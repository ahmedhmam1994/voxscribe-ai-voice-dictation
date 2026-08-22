"""Update checking against GitHub Releases.

Still deliberately does NOT auto-*install* -- overwriting a running .exe and
handling elevation is real risk for a hobby-scale app, and Inno Setup's own
installer already handles that safely when run normally. What this does add:
one-click *download* of the installer asset straight to Downloads (skipping
the browser), so running it is one click away instead of several -- the
user still explicitly launches the installer themselves, same as if they'd
downloaded it by hand. Uses stdlib urllib rather than adding a `requests`
dependency, since VoxScribe.spec already goes out of its way to keep the
packaged bundle small (see the v1.3 packaging fix in the project history).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.version import __version__

RELEASES_API_URL = (
    "https://api.github.com/repos/ahmedhmam1994/voxscribe-ai-voice-dictation/releases/latest"
)
RELEASES_PAGE_URL = (
    "https://github.com/ahmedhmam1994/voxscribe-ai-voice-dictation/releases/latest"
)
REQUEST_TIMEOUT_SEC = 6


def _parse_version(tag: str) -> tuple[int, ...]:
    """'v1.3' / '1.3' -> (1, 3). Stops at the first non-numeric run within a
    dot-separated part, so a suffix like '1.3-beta' still parses as (1, 3)."""
    tag = tag.strip().lstrip("vV")
    parts: list[int] = []
    for piece in tag.split("."):
        digits = ""
        for ch in piece:
            if not ch.isdigit():
                break
            digits += ch
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts) or (0,)


def is_newer(latest_tag: str, current: str = __version__) -> bool:
    return _parse_version(latest_tag) > _parse_version(current)


@dataclass
class UpdateInfo:
    version: str
    url: str
    # None if the release has no .exe asset attached (shouldn't normally
    # happen for this project, but the release page link still works either
    # way) -- callers must check before offering a one-click download.
    asset_url: str | None = None
    asset_name: str | None = None


class UpdateCheckThread(QThread):
    found = Signal(object)  # UpdateInfo
    none_found = Signal()
    failed = Signal(str)

    def run(self) -> None:
        try:
            req = urllib.request.Request(
                RELEASES_API_URL, headers={"Accept": "application/vnd.github+json"}
            )
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SEC) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            self.failed.emit(str(exc))
            return

        tag = data.get("tag_name", "")
        html_url = data.get("html_url") or RELEASES_PAGE_URL
        asset_url = None
        asset_name = None
        for asset in data.get("assets", []):
            name = asset.get("name", "")
            if name.lower().endswith(".exe"):
                asset_url = asset.get("browser_download_url")
                asset_name = name
                break
        if tag and is_newer(tag):
            self.found.emit(
                UpdateInfo(version=tag, url=html_url, asset_url=asset_url, asset_name=asset_name)
            )
        else:
            self.none_found.emit()


class UpdateDownloadThread(QThread):
    """Downloads the installer asset to the user's Downloads folder.
    Running it afterward is a separate, explicit user action (see
    MainWindow._on_tray_message_clicked) -- this thread never launches
    anything itself."""

    done = Signal(str)  # local file path
    failed = Signal(str)

    def __init__(self, asset_url: str, asset_name: str) -> None:
        super().__init__()
        self.asset_url = asset_url
        self.asset_name = asset_name

    def run(self) -> None:
        dest = Path.home() / "Downloads" / self.asset_name
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(self.asset_url, dest)  # noqa: S310 -- github release asset
        except (urllib.error.URLError, OSError, ValueError) as exc:
            self.failed.emit(str(exc))
            return
        self.done.emit(str(dest))
