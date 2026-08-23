"""Local-only dictation history -- a JSON-backed log of past transcriptions,
alongside the running counters in core/settings.py (which only ever tracked
totals, never individual entries). Powers the Insights page and the
Dictation page's history feed in app/main_window.py. Never transmitted
anywhere, same as core/crash_reporter.py's local-only logs.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

HISTORY_PATH = Path.home() / "AppData" / "Local" / "VoxScribe" / "history.json"

# Keeps the file from growing unbounded over months/years of daily use --
# far more than the UI ever needs to show at once, but enough to compute
# meaningful stats (streak, totals) without unbounded disk growth.
_MAX_ENTRIES = 2000


@dataclass
class HistoryEntry:
    timestamp: str  # ISO 8601, local time
    text: str
    words: int
    duration_seconds: float

    def local_datetime(self) -> datetime:
        return datetime.fromisoformat(self.timestamp)


def _load() -> list[HistoryEntry]:
    if not HISTORY_PATH.exists():
        return []
    try:
        raw = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    entries = []
    for item in raw:
        try:
            entries.append(HistoryEntry(**item))
        except TypeError:
            continue  # skip malformed rows rather than losing the whole file
    return entries


def _save(entries: list[HistoryEntry]) -> None:
    try:
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_PATH.write_text(
            json.dumps([asdict(e) for e in entries[-_MAX_ENTRIES:]], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        # A history write failure must never block the dictation flow itself.
        pass


def add_entry(text: str, duration_seconds: float) -> None:
    """Called once per successful (non-empty) transcription -- mirrors
    core/settings.py's record_dictation(), which callers still call
    separately for the running totals."""
    entries = _load()
    entries.append(
        HistoryEntry(
            timestamp=datetime.now().isoformat(timespec="seconds"),
            text=text,
            words=len(text.split()),
            duration_seconds=duration_seconds,
        )
    )
    _save(entries)


def get_recent(limit: int = 50) -> list[HistoryEntry]:
    """Newest first."""
    return list(reversed(_load()))[:limit]


def get_today(limit: int = 100) -> list[HistoryEntry]:
    today = date.today()
    return [e for e in get_recent(limit=_MAX_ENTRIES) if e.local_datetime().date() == today][:limit]


def compute_stats() -> dict:
    """Total words, average words-per-minute across all recorded sessions,
    and the current day streak (consecutive days with at least one
    dictation, counting back from today)."""
    entries = _load()
    total_words = sum(e.words for e in entries)

    total_minutes = sum(e.duration_seconds for e in entries) / 60
    wpm = round(total_words / total_minutes) if total_minutes > 0 else 0

    days_with_activity = {e.local_datetime().date() for e in entries}
    streak = 0
    cursor = date.today()
    while cursor in days_with_activity:
        streak += 1
        cursor -= timedelta(days=1)

    return {"total_words": total_words, "wpm": wpm, "streak_days": streak}
