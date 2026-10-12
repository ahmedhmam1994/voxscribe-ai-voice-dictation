"""Pure helpers for importing many audio or video files in one go.

Kept free of Qt and Whisper so the file picking, the progress maths and the
summary text can be unit tested on their own.
"""

from __future__ import annotations

import os
from pathlib import Path

MEDIA_EXTENSIONS = (
    ".wav", ".mp3", ".m4a", ".mp4", ".mov", ".flac", ".ogg", ".wma", ".aac", ".webm",
)  # fmt: skip


def is_media(path: str) -> bool:
    return Path(path).suffix.lower() in MEDIA_EXTENSIONS


def collect_media(paths: list[str]) -> list[str]:
    """Expands folders (including their subfolders) into media files and drops
    anything that is not audio or video. Order is stable and duplicates go."""
    found: list[str] = []
    seen: set[str] = set()

    def add(candidate: str) -> None:
        key = os.path.normcase(os.path.abspath(candidate))
        if key not in seen and is_media(candidate):
            seen.add(key)
            found.append(candidate)

    for path in paths:
        if os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                dirs.sort()
                for name in sorted(files):
                    add(os.path.join(root, name))
        elif os.path.isfile(path):
            add(path)
    return found


def split_done(files: list[str]) -> tuple[list[str], list[str]]:
    """Separates files that already have an .srt next to them (done on an
    earlier run) from the ones still to do."""
    todo, skipped = [], []
    for path in files:
        (skipped if Path(path).with_suffix(".srt").exists() else todo).append(path)
    return todo, skipped


def overall_percent(finished: int, total: int, current_percent: float) -> int:
    """Whole batch progress: finished files plus the part done of the current one."""
    if total <= 0:
        return 0
    value = (finished * 100 + max(0.0, min(100.0, current_percent))) / total
    return int(max(0, min(100, value)))


def common_folder(paths: list[str]) -> str | None:
    """The folder that holds all the given files, for an Open folder button."""
    if not paths:
        return None
    try:
        return os.path.commonpath([os.path.dirname(os.path.abspath(p)) for p in paths])
    except ValueError:  # files on different drives
        return os.path.dirname(os.path.abspath(paths[0]))


def format_summary(
    total: int, done: int, failed: int, skipped: int, saved_srt: int, cancelled: bool
) -> str:
    head = (
        f"Batch stopped: {done} of {total} files transcribed"
        if cancelled
        else f"Batch done: {done} of {total} files transcribed"
    )
    parts = [head]
    if saved_srt:
        parts.append(f"{saved_srt} .srt saved")
    if failed:
        parts.append(f"{failed} failed")
    if skipped:
        parts.append(f"{skipped} skipped (already had an .srt)")
    return ", ".join(parts) + "."
