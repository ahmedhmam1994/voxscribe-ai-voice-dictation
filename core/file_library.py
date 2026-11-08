"""Recent file and link transcripts, kept on this PC so the Files page can
show them again after the app restarts.

One small JSON file per transcript in the app data folder (like history.json
for dictations, nothing leaves the PC). Only the newest MAX_ENTRIES are kept.
Pure Python, no Qt, so it is tested on its own.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

LIBRARY_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "VoxScribe" / "library"
MAX_ENTRIES = 200

KIND_FILE = "file"
KIND_LINK = "link"
KIND_CAPTIONS = "captions"
KIND_LABELS = {KIND_FILE: "File", KIND_LINK: "Link", KIND_CAPTIONS: "Site captions"}


@dataclass(frozen=True)
class Entry:
    id: str
    title: str
    source: str  # the file path or the web link
    kind: str
    created: float
    text: str

    @property
    def words(self) -> int:
        return len(self.text.split())

    @property
    def label(self) -> str:
        return KIND_LABELS.get(self.kind, "File")


def _folder(folder: Path | None) -> Path:
    return folder or LIBRARY_DIR


def add(
    title: str, source: str, kind: str, text: str, *, folder: Path | None = None
) -> Entry | None:
    """Keeps a transcript. Returns None (and keeps nothing) for empty text,
    or when the folder cannot be written; the import itself never fails."""
    if not text.strip():
        return None
    entry = Entry(
        id=f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:6]}",
        title=title.strip() or "Untitled",
        source=source,
        kind=kind if kind in KIND_LABELS else KIND_FILE,
        created=time.time(),
        text=text.strip(),
    )
    base = _folder(folder)
    try:
        base.mkdir(parents=True, exist_ok=True)
        (base / f"{entry.id}.json").write_text(
            json.dumps(asdict(entry), ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        return None
    _prune(base)
    return entry


def _read(path: Path) -> Entry | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return Entry(
            id=str(raw["id"]),
            title=str(raw["title"]),
            source=str(raw.get("source", "")),
            kind=str(raw.get("kind", KIND_FILE)),
            created=float(raw["created"]),
            text=str(raw["text"]),
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _files(base: Path) -> list[Path]:
    try:
        return sorted(base.glob("*.json"), key=lambda p: p.name, reverse=True)
    except OSError:
        return []


def recent(limit: int = 50, *, folder: Path | None = None) -> list[Entry]:
    """Newest first. Damaged files are skipped."""
    entries = []
    for path in _files(_folder(folder)):
        entry = _read(path)
        if entry is not None:
            entries.append(entry)
        if len(entries) >= limit:
            break
    entries.sort(key=lambda e: e.created, reverse=True)
    return entries


def get(entry_id: str, *, folder: Path | None = None) -> Entry | None:
    if not _safe_id(entry_id):
        return None
    return _read(_folder(folder) / f"{entry_id}.json")


def delete(entry_id: str, *, folder: Path | None = None) -> None:
    if _safe_id(entry_id):
        (_folder(folder) / f"{entry_id}.json").unlink(missing_ok=True)


def clear(*, folder: Path | None = None) -> None:
    for path in _files(_folder(folder)):
        path.unlink(missing_ok=True)


def _prune(base: Path) -> None:
    for path in _files(base)[MAX_ENTRIES:]:
        path.unlink(missing_ok=True)


def _safe_id(entry_id: str) -> bool:
    """Ids are only digits, letters and a dash, so they can never point
    outside the library folder."""
    return bool(entry_id) and all(ch.isalnum() or ch == "-" for ch in entry_id)


def when(entry: Entry, now: float | None = None) -> str:
    """'Today 3:05 PM', 'Yesterday 9:10 AM' or '4 Nov 2:00 PM'."""
    now = time.time() if now is None else now
    then = time.localtime(entry.created)
    today = time.localtime(now)
    clock = time.strftime("%I:%M %p", then).lstrip("0")
    days = (
        time.mktime((today.tm_year, today.tm_mon, today.tm_mday, 0, 0, 0, 0, 0, -1))
        - time.mktime((then.tm_year, then.tm_mon, then.tm_mday, 0, 0, 0, 0, 0, -1))
    ) // 86400
    if days <= 0:
        return f"Today {clock}"
    if days == 1:
        return f"Yesterday {clock}"
    return f"{then.tm_mday} {time.strftime('%b', then)} {clock}"
