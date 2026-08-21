"""Local-only crash logging -- no telemetry, nothing leaves the device.

VoxScribe.spec sets console=False, so an unhandled exception in the packaged
.exe would otherwise vanish with no trace to debug from. This installs a
global excepthook that writes uncaught exceptions to a local log file
instead. Logs are never uploaded automatically -- see docs/privacy.html.
Use the tray menu's "Open Logs Folder" to find one and attach it to a
GitHub issue by hand, if you choose to.
"""

from __future__ import annotations

import platform
import sys
import traceback
from datetime import datetime
from pathlib import Path

from app.version import __version__

LOG_DIR = Path.home() / "AppData" / "Local" / "VoxScribe" / "logs"


def _write_crash_log(exc_type, exc_value, exc_tb) -> None:  # noqa: ANN001
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        path = LOG_DIR / f"crash_{datetime.now():%Y%m%d_%H%M%S}.log"
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"VoxScribe {__version__} crash report\n")
            f.write(f"Time: {datetime.now().isoformat()}\n")
            f.write(f"Platform: {platform.platform()}\n")
            f.write(f"Python: {sys.version}\n\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    except OSError:
        # Logging the crash must never itself crash harder or block the
        # original exception from still reaching the previous hook.
        pass


def install() -> None:
    previous_hook = sys.excepthook

    def _hook(exc_type, exc_value, exc_tb):  # noqa: ANN001
        _write_crash_log(exc_type, exc_value, exc_tb)
        previous_hook(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook
