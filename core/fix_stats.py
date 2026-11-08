"""Counts for the Insights page's "Learning your words" row: how often you
still have to fix a word, how many fixes VoxScribe learned, and how many words
your word lists and learned words corrected for you.

Only numbers per day are kept (never a word or a sentence), in a small JSON
file on this PC. Nothing is sent anywhere.

    {"2026-11-08": {"hand": 2, "redo": 1, "learned": 2, "auto": 14}}

- hand: a word you fixed yourself in the app you dictated into
- redo: Try harder pressed
- learned: a fix kept by core/learned_words.py
- auto: words changed for you by word replacements, learned words and packs
"""

from __future__ import annotations

import difflib
import json
import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

STATS_PATH = (
    Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "VoxScribe" / "fix_stats.json"
)
KINDS = ("hand", "redo", "learned", "auto")
KEEP_DAYS = 400
TREND_WEEKS = 8
# A week with fewer dictated words than this gives no rate: two fixes in fifty
# words would look like a disaster.
MIN_WEEK_WORDS = 200


def _load() -> dict[str, dict[str, int]]:
    try:
        raw = json.loads(STATS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    days = {}
    for day, counts in raw.items():
        if isinstance(day, str) and isinstance(counts, dict):
            days[day] = {k: int(v) for k, v in counts.items() if k in KINDS and isinstance(v, int)}
    return days


def _save(days: dict[str, dict[str, int]]) -> None:
    kept = dict(sorted(days.items())[-KEEP_DAYS:])
    try:
        STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATS_PATH.write_text(json.dumps(kept, indent=1), encoding="utf-8")
    except OSError:
        pass  # a count must never get in the way of dictation


def record(kind: str, count: int = 1, today: date | None = None) -> None:
    if kind not in KINDS or count <= 0:
        return
    day = (today or date.today()).isoformat()
    days = _load()
    counts = days.setdefault(day, {})
    counts[kind] = counts.get(kind, 0) + count
    _save(days)


def changed_words(before: str, after: str) -> int:
    """How many words of `before` were swapped for something else in `after`."""
    old, new = before.split(), after.split()
    if old == new:
        return 0
    changed = 0
    matcher = difflib.SequenceMatcher(None, old, new, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "replace":
            changed += max(i2 - i1, j2 - j1)
    return changed


@dataclass
class LearningStats:
    learned_week: int
    learned_total: int
    auto_week: int
    auto_total: int
    # Fixes you made per 1,000 dictated words, one per week, oldest first;
    # None for a week with too few words to tell.
    rates: list[float | None]
    # False until anything at all was counted, so Insights can hide the row.
    has_data: bool = False

    @property
    def rate_now(self) -> float | None:
        return self.rates[-1] if self.rates else None

    @property
    def rate_before(self) -> float | None:
        """The rate about a month ago: 4 weeks back, else the nearest known
        one before that."""
        for rate in reversed(self.rates[:-4]):
            if rate is not None:
                return rate
        return None


def compute(words_by_day: dict[date, int], today: date | None = None) -> LearningStats:
    """`words_by_day` comes from core/history.py, so the rate uses the same
    dictated words as the rest of the Insights page."""
    today = today or date.today()
    days = _load()

    def total(kind: str, start: date | None = None) -> int:
        return sum(
            counts.get(kind, 0)
            for day, counts in days.items()
            if start is None or day >= start.isoformat()
        )

    week_start = today - timedelta(days=6)
    rates: list[float | None] = []
    for back in range(TREND_WEEKS - 1, -1, -1):
        end = today - timedelta(days=7 * back)
        start = end - timedelta(days=6)
        words = sum(n for d, n in words_by_day.items() if start <= d <= end)
        fixes = sum(
            counts.get("hand", 0) + counts.get("redo", 0)
            for day, counts in days.items()
            if start.isoformat() <= day <= end.isoformat()
        )
        rates.append(round(fixes * 1000 / words, 1) if words >= MIN_WEEK_WORDS else None)
    return LearningStats(
        learned_week=total("learned", week_start),
        learned_total=total("learned"),
        auto_week=total("auto", week_start),
        auto_total=total("auto"),
        rates=rates,
        has_data=bool(days),
    )
