"""Dev-only: copies the license signing key to the clipboard, base64, without showing it.

Used once, to set up tools/apps-script-fulfillment: paste the result into the Apps
Script property SIGNING_SEED_B64. The key is never printed, so it does not end up in
a terminal history or a chat log. Clear the clipboard afterwards (copy anything else).

Usage:
    venv\\Scripts\\python.exe scripts\\copy_signing_key.py
"""

from __future__ import annotations

import base64
import subprocess
import sys
from pathlib import Path

_KEY_FILE = Path(__file__).resolve().parent.parent / "license_signing_key.raw"


def main() -> int:
    if not _KEY_FILE.exists():
        print(f"Missing {_KEY_FILE.name}.")
        return 1
    encoded = base64.b64encode(_KEY_FILE.read_bytes())
    subprocess.run(["clip"], input=encoded, check=True)
    print("Copied the signing key to the clipboard (base64). Paste it into Script Properties.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
