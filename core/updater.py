"""Update checking against GitHub Releases.

Deliberately does NOT auto-download/auto-install (overwriting a running
.exe and handling elevation is a lot of real risk for a hobby-scale app) --
just "a newer version exists, here's the link", surfaced via the tray.
Uses stdlib urllib rather than adding a `requests` dependency, since
VoxScribe.spec already goes out of its way to keep the packaged bundle
small (see the v1.3 packaging fix in the project history).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

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
        if tag and is_newer(tag):
            self.found.emit(UpdateInfo(version=tag, url=html_url))
        else:
            self.none_found.emit()
