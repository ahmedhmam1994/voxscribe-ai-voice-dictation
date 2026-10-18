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


def replace_last_text(old: str, new: str) -> None:
    """Swaps the newest entry's text after Try harder retyped it, so the
    history shows what is really in the document. Does nothing if the newest
    entry is not `old` (another dictation came in meanwhile)."""
    entries = _load()
    if not entries or entries[-1].text != old:
        return
    entries[-1].text = new
    entries[-1].words = len(new.split())
    _save(entries)


def get_recent(limit: int = 50) -> list[HistoryEntry]:
    """Newest first."""
    return list(reversed(_load()))[:limit]


def get_today(limit: int = 100) -> list[HistoryEntry]:
    today = date.today()
    return [e for e in get_recent(limit=_MAX_ENTRIES) if e.local_datetime().date() == today][:limit]


# A typical typing speed, used only for the Insights "typing saved" estimate.
TYPING_WPM = 40
ACTIVITY_WEEKS = 12


@dataclass
class Insights:
    """Everything the Insights page shows, worked out from the saved history."""

    total_words: int
    dictations: int
    wpm: int
    streak_days: int
    today_words: int
    today_dictations: int
    minutes_saved: float
    # Words per day for the last 7 days, oldest first; the last one is today.
    week: list[int]
    # True for each of the last 7 days that had a dictation, oldest first.
    week_active: list[bool]
    # Words per day from activity_start (a Monday) to today, for the grid.
    activity_start: date
    activity: list[int]
    longest_words: int
    longest_seconds: float
    # Hour of the day (0-23) with the most words, or None with too little data.
    busiest_hour: int | None


def compute_insights(
    entries: list[HistoryEntry] | None = None, today: date | None = None
) -> Insights:
    """All the numbers for the Insights page in one pass. `entries` and
    `today` are only passed in tests."""
    if entries is None:
        entries = _load()
    if today is None:
        today = date.today()

    words_by_day: dict[date, int] = {}
    words_by_hour: dict[int, int] = {}
    for e in entries:
        moment = e.local_datetime()
        words_by_day[moment.date()] = words_by_day.get(moment.date(), 0) + e.words
        words_by_hour[moment.hour] = words_by_hour.get(moment.hour, 0) + e.words

    total_words = sum(e.words for e in entries)
    talk_minutes = sum(e.duration_seconds for e in entries) / 60
    wpm = round(total_words / talk_minutes) if talk_minutes > 0 else 0

    streak = 0
    cursor = today
    while cursor in words_by_day:
        streak += 1
        cursor -= timedelta(days=1)

    week_days = [today - timedelta(days=6 - i) for i in range(7)]
    # The grid starts on a Monday so each column is one calendar week.
    first = today - timedelta(weeks=ACTIVITY_WEEKS - 1)
    activity_start = first - timedelta(days=first.weekday())
    span = (today - activity_start).days + 1

    longest = max(entries, key=lambda e: e.words, default=None)
    today_entries = [e for e in entries if e.local_datetime().date() == today]

    return Insights(
        total_words=total_words,
        dictations=len(entries),
        wpm=wpm,
        streak_days=streak,
        today_words=sum(e.words for e in today_entries),
        today_dictations=len(today_entries),
        minutes_saved=max(0.0, total_words / TYPING_WPM - talk_minutes),
        week=[words_by_day.get(d, 0) for d in week_days],
        week_active=[d in words_by_day for d in week_days],
        activity_start=activity_start,
        activity=[words_by_day.get(activity_start + timedelta(days=i), 0) for i in range(span)],
        longest_words=longest.words if longest else 0,
        longest_seconds=longest.duration_seconds if longest else 0.0,
        busiest_hour=(
            max(words_by_hour, key=lambda h: words_by_hour[h]) if len(entries) >= 3 else None
        ),
    )


def format_minutes_saved(minutes: float) -> str:
    """142.5 -> "2 h 22 min", 12.2 -> "12 min", 0.4 -> "under a minute"."""
    if minutes < 1:
        return "under a minute"
    whole = int(round(minutes))
    hours, mins = divmod(whole, 60)
    if hours == 0:
        return f"{mins} min"
    return f"{hours} h {mins} min" if mins else f"{hours} h"


def format_hour(hour: int) -> str:
    """0 -> "midnight", 9 -> "9 am", 12 -> "noon", 15 -> "3 pm"."""
    if hour == 0:
        return "midnight"
    if hour == 12:
        return "noon"
    return f"{hour} am" if hour < 12 else f"{hour - 12} pm"


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
