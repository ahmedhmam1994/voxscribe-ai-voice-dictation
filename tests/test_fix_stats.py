from datetime import date, timedelta

import pytest

from core import fix_stats

TODAY = date(2026, 11, 8)


@pytest.fixture(autouse=True)
def stats_file(monkeypatch, tmp_path):
    monkeypatch.setattr(fix_stats, "STATS_PATH", tmp_path / "fix_stats.json")


def test_counts_are_kept_per_day_and_kind():
    fix_stats.record("learned", today=TODAY)
    fix_stats.record("learned", today=TODAY)
    fix_stats.record("auto", 5, today=TODAY - timedelta(days=10))
    fix_stats.record("nonsense", today=TODAY)
    stats = fix_stats.compute({}, TODAY)
    assert stats.learned_week == 2 and stats.learned_total == 2
    assert stats.auto_week == 0 and stats.auto_total == 5


def test_the_rate_is_fixes_per_thousand_words_a_week():
    words = {TODAY - timedelta(days=d): 100 for d in range(56)}  # 700 a week
    fix_stats.record("hand", 7, today=TODAY)
    fix_stats.record("redo", 7, today=TODAY - timedelta(days=30))
    stats = fix_stats.compute(words, TODAY)
    assert len(stats.rates) == fix_stats.TREND_WEEKS
    assert stats.rate_now == 10.0
    # The Try harder 30 days ago falls in the week four weeks back.
    assert stats.rate_before == 10.0
    assert stats.rates[-2] == 0.0


def test_a_quiet_week_gives_no_rate():
    stats = fix_stats.compute({TODAY: 50}, TODAY)
    assert stats.rate_now is None and stats.rate_before is None


def test_changed_words_counts_swaps_not_additions():
    assert fix_stats.changed_words("tell shivon hi", "tell Siobhan hi") == 1
    assert fix_stats.changed_words("a b c", "a b c") == 0
    assert fix_stats.changed_words("vox scribe rocks", "VoxScribe rocks") == 2
    assert fix_stats.changed_words("hello", "hello there") == 0


def test_a_damaged_file_counts_as_empty(tmp_path):
    fix_stats.STATS_PATH.write_text("not json", encoding="utf-8")
    assert fix_stats.compute({}, TODAY).learned_total == 0
    fix_stats.record("hand", today=TODAY)
    assert fix_stats.compute({}, TODAY).learned_total == 0
