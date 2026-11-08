"""The Library: everything you said or imported, in one list you can search.

It reads the stores that already exist, so nothing is copied or migrated:

- dictations: core/history.py
- files, links and site captions: core/file_library.py
- the notes inbox: the markdown file of core/inbox.py
- meeting notes: the markdown files of core/meeting_notes.py

All of it stays on this PC. "Keep for" decides how long dictations and file
transcripts are kept (forever by default). Inbox and meeting notes are your
own files, often inside a notes vault, so the Library only reads them and
never deletes or trims them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QSettings

from core import file_library, history, settings

KIND_DICTATION = "dictation"
KIND_FILE = "file"
KIND_INBOX = "inbox"
KIND_MEETING = "meeting"

# The type filters on the page, in order. Files covers links and captions too.
FILTERS = (
    (None, "All"),
    (KIND_DICTATION, "Dictations"),
    (KIND_FILE, "Files and links"),
    (KIND_INBOX, "Notes inbox"),
    (KIND_MEETING, "Meetings"),
)
SINCE = ((None, "Any time"), (0, "Today"), (7, "7 days"), (30, "30 days"))

# Keep for: days, None for forever, 0 for off (counts only, for Insights).
KEEP_FOREVER = None
KEEP_OFF = 0
KEEP_CHOICES = ((KEEP_FOREVER, "Forever"), (90, "90 days"), (30, "30 days"), (KEEP_OFF, "Off"))

_MAX_MEETING_BYTES = 2_000_000
_INBOX_DAY = re.compile(r"^## (\d{4}-\d{2}-\d{2})\s*$")
_INBOX_LINE = re.compile(r"^- (\d{1,2}:\d{2}) (.+)$")
_MEETING_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\d{2})-(\d{2}) Meeting")
_FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


@dataclass
class Item:
    id: str
    kind: str
    label: str
    title: str
    text: str
    created: datetime
    source: str = ""
    # Dictations and file transcripts can be deleted here; inbox and meeting
    # notes are your own files.
    deletable: bool = False

    @property
    def words(self) -> int:
        return len(self.text.split())


def _settings() -> QSettings:
    return QSettings("VoxScribe", "VoxScribe")


def get_keep_days() -> int | None:
    """How long dictations and file transcripts are kept: None is forever."""
    value = _settings().value("library_keep_days", "")
    try:
        days = int(value)
    except (TypeError, ValueError):
        return KEEP_FOREVER
    return days if days in {d for d, _ in KEEP_CHOICES if d is not None} else KEEP_FOREVER


def set_keep_days(days: int | None) -> None:
    _settings().setValue("library_keep_days", "" if days is None else str(days))


def keeps_text() -> bool:
    """False when Keep for is Off: nothing said or imported is kept."""
    return get_keep_days() != KEEP_OFF


def apply_retention(now: datetime | None = None) -> int:
    """Removes dictations and file transcripts older than Keep for allows.
    Dictations keep their counts for Insights. Returns how many went."""
    days = get_keep_days()
    if days is KEEP_FOREVER:
        return 0
    now = now or datetime.now()
    cutoff = None if days == KEEP_OFF else now - timedelta(days=days)
    gone = history.forget_text_before(cutoff)
    gone += file_library.delete_before(None if cutoff is None else cutoff.timestamp())
    return gone


def _title(text: str, limit: int = 80) -> str:
    line = " ".join(text.split())
    return line if len(line) <= limit else line[: limit - 3].rstrip() + "..."


def _dictations() -> list[Item]:
    items = []
    for number, entry in enumerate(history.get_recent(limit=100_000)):
        if not entry.text.strip():
            continue
        try:
            created = entry.local_datetime()
        except ValueError:
            continue
        items.append(
            Item(
                id=f"d|{entry.timestamp}|{number}",
                kind=KIND_DICTATION,
                label="Dictation",
                title=_title(entry.text),
                text=entry.text,
                created=created,
                deletable=True,
            )
        )
    return items


def _files() -> list[Item]:
    return [
        Item(
            id=f"f|{entry.id}",
            kind=KIND_FILE,
            label=entry.label,
            title=entry.title,
            text=entry.text,
            created=datetime.fromtimestamp(entry.created),
            source=entry.source,
            deletable=True,
        )
        for entry in file_library.recent(file_library.MAX_ENTRIES)
    ]


def parse_inbox(text: str, source: str = "") -> list[Item]:
    """One item per "- 14:32 note" line under its "## 2026-10-28" heading."""
    items = []
    day = None
    for number, line in enumerate(text.splitlines()):
        heading = _INBOX_DAY.match(line)
        if heading:
            day = heading.group(1)
            continue
        note = _INBOX_LINE.match(line)
        if not note or day is None:
            continue
        try:
            created = datetime.strptime(f"{day} {note.group(1)}", "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        said = note.group(2).strip()
        items.append(
            Item(
                id=f"i|{number}",
                kind=KIND_INBOX,
                label="Inbox note",
                title=_title(said),
                text=said,
                created=created,
                source=source,
            )
        )
    return items


def _inbox() -> list[Item]:
    path = Path(settings.get_inbox_path())
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return parse_inbox(text, str(path))


def meeting_item(path: Path, text: str) -> Item | None:
    """A meeting note file as an item, dated by its file name."""
    name = _MEETING_NAME.match(path.stem)
    if not name:
        return None
    try:
        created = datetime.strptime(
            f"{name.group(1)} {name.group(2)}:{name.group(3)}", "%Y-%m-%d %H:%M"
        )
    except ValueError:
        return None
    body = _FRONT_MATTER.sub("", text.replace("\r\n", "\n"), count=1).strip()
    return Item(
        id=f"m|{path.name}",
        kind=KIND_MEETING,
        label="Meeting",
        title=f"Meeting {created:%Y-%m-%d %H:%M}",
        text=body,
        created=created,
        source=str(path),
    )


def _meetings() -> list[Item]:
    folder = Path(settings.get_meeting_folder())
    items = []
    try:
        paths = list(folder.glob("*Meeting*.md"))
    except OSError:
        return []
    for path in paths:
        try:
            if path.stat().st_size > _MAX_MEETING_BYTES:
                continue
            item = meeting_item(path, path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        if item is not None:
            items.append(item)
    return items


def all_items() -> list[Item]:
    """Everything, newest first."""
    items = _dictations() + _files() + _inbox() + _meetings()
    items.sort(key=lambda item: item.created, reverse=True)
    return items


def search(
    items: list[Item],
    query: str = "",
    kind: str | None = None,
    since_days: int | None = None,
    now: datetime | None = None,
) -> list[Item]:
    """Items with every word of `query` in their title or text (any case),
    of `kind`, made today (0) or in the last `since_days` days."""
    words = query.casefold().split()
    start = None
    if since_days is not None:
        today = (now or datetime.now()).replace(hour=0, minute=0, second=0, microsecond=0)
        start = today - timedelta(days=since_days)
    found = []
    for item in items:
        if kind is not None and item.kind != kind:
            continue
        if start is not None and item.created < start:
            continue
        if words:
            haystack = f"{item.title}\n{item.text}".casefold()
            if not all(word in haystack for word in words):
                continue
        found.append(item)
    return found


def delete(item: Item) -> bool:
    """Deletes a dictation's words or a file transcript. Inbox and meeting
    notes are never deleted from here."""
    if item.kind == KIND_DICTATION:
        timestamp = item.id.split("|")[1]
        return history.forget_text(timestamp, item.text)
    if item.kind == KIND_FILE:
        file_library.delete(item.id.split("|", 1)[1])
        return True
    return False


def when(item: Item, now: float | None = None) -> str:
    """'Today 3:05 PM', 'Yesterday 9:10 AM' or '4 Nov 2:00 PM'."""
    stub = file_library.Entry("", "", "", "", item.created.timestamp(), "")
    return file_library.when(stub, now)


_MARKDOWN = re.compile(r"^\s*(?:#+\s*|[-*]\s+\[[ xX]\]\s*|[-*]\s+|>\s*)|\*\*|__", re.MULTILINE)


def plain(text: str) -> str:
    """Text without markdown marks (headings, list bullets, checkboxes, bold),
    on one line, for showing a piece of a note."""
    return " ".join(_MARKDOWN.sub("", text).split())


def snippet(item: Item, query: str, width: int = 120) -> str:
    """A short piece of the text around the first search word, or its start,
    cut at word edges."""
    text = plain(item.text)
    words = query.casefold().split()
    at = text.casefold().find(words[0]) if words else -1
    if at < 0 or len(text) <= width:
        return text[:width].rsplit(" ", 1)[0] + "..." if len(text) > width else text
    start = max(0, at - width // 3)
    if start:
        space = text.find(" ", start)
        start = space + 1 if 0 <= space < at else start
    end = min(len(text), start + width)
    if end < len(text):
        space = text.rfind(" ", start, end)
        end = space if space > at else end
    return ("..." if start else "") + text[start:end] + ("..." if end < len(text) else "")
