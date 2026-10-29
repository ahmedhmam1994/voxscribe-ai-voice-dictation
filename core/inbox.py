"""The notes inbox: a second hotkey that saves what you say to a markdown file
instead of typing it. Point the file at a folder inside an Obsidian vault (or
any notes app that reads markdown) and your spoken thoughts land there with the
time they were said:

    # VoxScribe Inbox

    ## 2026-10-28
    - 14:32 Call the clinic about the lab results
    - 14:40 Idea: show unsure words in the transcript

Plain text on this PC, appended one line at a time, never rewritten.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

FILE_NAME = "VoxScribe Inbox.md"
_TITLE = "# VoxScribe Inbox"


def default_path() -> Path:
    return Path.home() / "Documents" / FILE_NAME


def _one_line(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _last_day_heading(path: Path) -> str | None:
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - 4096))
            tail = handle.read().decode("utf-8", errors="ignore")
    except OSError:
        return None
    headings = re.findall(r"^## (\d{4}-\d{2}-\d{2})\s*$", tail, flags=re.MULTILINE)
    return headings[-1] if headings else None


def append_note(path: Path, text: str, now: datetime | None = None) -> bool:
    """Adds one line for `text`. Creates the file and its folder when missing.
    Returns False (and writes nothing) for empty text. Raises OSError when the
    file cannot be written, so the caller can say so."""
    line = _one_line(text)
    if not line:
        return False
    now = now or datetime.now()
    day = now.strftime("%Y-%m-%d")
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    chunks = []
    if not exists:
        chunks.append(f"{_TITLE}\n\n")
    elif not path.read_bytes().endswith(b"\n"):
        chunks.append("\n")
    if not exists or _last_day_heading(path) != day:
        chunks.append(f"## {day}\n")
    chunks.append(f"- {now.strftime('%H:%M')} {line}\n")
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write("".join(chunks))
    return True
