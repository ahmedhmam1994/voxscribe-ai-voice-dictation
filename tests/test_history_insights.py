"""Tests for the Insights numbers in core/history.py."""

from datetime import date, datetime, timedelta

from core.history import (
    HistoryEntry,
    compute_insights,
    format_hour,
    format_minutes_saved,
)

TODAY = date(2026, 10, 18)  # a Sunday


def _entry(day: date, hour: int, words: int, seconds: float) -> HistoryEntry:
    when = datetime(day.year, day.month, day.day, hour, 0, 0)
    return HistoryEntry(
        timestamp=when.isoformat(), text="x " * words, words=words, duration_seconds=seconds
    )


def test_empty_history():
    ins = compute_insights([], TODAY)
    assert ins.total_words == 0
    assert ins.wpm == 0
    assert ins.streak_days == 0
    assert ins.week == [0] * 7
    assert ins.busiest_hour is None
    assert ins.longest_words == 0
    assert ins.minutes_saved == 0


def test_totals_speed_and_today():
    entries = [
        _entry(TODAY, 10, 100, 60),
        _entry(TODAY, 11, 50, 30),
        _entry(TODAY - timedelta(days=1), 10, 150, 90),
    ]
    ins = compute_insights(entries, TODAY)
    assert ins.total_words == 300
    assert ins.dictations == 3
    assert ins.wpm == 100  # 300 words in 3 minutes
    assert ins.today_words == 150
    assert ins.today_dictations == 2
    assert ins.streak_days == 2


def test_typing_saved_is_typing_time_minus_talking_time():
    # 400 words take 10 minutes to type at 40 wpm; saying them took 2.
    ins = compute_insights([_entry(TODAY, 9, 400, 120)], TODAY)
    assert abs(ins.minutes_saved - 8.0) < 1e-9


def test_typing_saved_never_negative():
    ins = compute_insights([_entry(TODAY, 9, 5, 600)], TODAY)
    assert ins.minutes_saved == 0


def test_week_is_oldest_first_and_ends_today():
    entries = [_entry(TODAY, 9, 7, 5), _entry(TODAY - timedelta(days=6), 9, 3, 5)]
    ins = compute_insights(entries, TODAY)
    assert ins.week == [3, 0, 0, 0, 0, 0, 7]
    assert ins.week_active == [True, False, False, False, False, False, True]


def test_streak_breaks_on_a_missed_day():
    entries = [_entry(TODAY, 9, 1, 1), _entry(TODAY - timedelta(days=2), 9, 1, 1)]
    assert compute_insights(entries, TODAY).streak_days == 1


def test_activity_grid_starts_on_a_monday_and_ends_today():
    entries = [_entry(TODAY, 9, 12, 5)]
    ins = compute_insights(entries, TODAY)
    assert ins.activity_start.weekday() == 0
    assert ins.activity_start + timedelta(days=len(ins.activity) - 1) == TODAY
    assert ins.activity[-1] == 12
    # 12 calendar weeks; today is a Sunday, so every column is full.
    assert len(ins.activity) == 84


def test_busiest_hour_needs_a_few_dictations():
    two = [_entry(TODAY, 9, 10, 5), _entry(TODAY, 15, 30, 5)]
    assert compute_insights(two, TODAY).busiest_hour is None
    three = two + [_entry(TODAY, 15, 5, 5)]
    assert compute_insights(three, TODAY).busiest_hour == 15


def test_longest_dictation():
    entries = [_entry(TODAY, 9, 10, 5), _entry(TODAY, 10, 80, 40)]
    ins = compute_insights(entries, TODAY)
    assert ins.longest_words == 80
    assert ins.longest_seconds == 40


def test_format_minutes_saved():
    assert format_minutes_saved(0.4) == "under a minute"
    assert format_minutes_saved(12.2) == "12 min"
    assert format_minutes_saved(60) == "1 h"
    assert format_minutes_saved(142.5) == "2 h 22 min"


def test_format_hour():
    assert format_hour(0) == "midnight"
    assert format_hour(9) == "9 am"
    assert format_hour(12) == "noon"
    assert format_hour(15) == "3 pm"
