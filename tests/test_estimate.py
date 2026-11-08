"""Tests for core/estimate.py."""

from core import estimate


def test_lengths_read_naturally():
    assert estimate.describe_length(42) == "42 s"
    assert estimate.describe_length(18 * 60 + 20) == "18 min"
    assert estimate.describe_length(80 * 60) == "1 h 20 min"
    assert estimate.describe_length(120 * 60) == "2 h"


def test_time_uses_the_learned_speed():
    assert estimate.transcribe_time(1200, 0.25) == "about 5 min"
    assert estimate.transcribe_time(3, 0.25) == "about 5 s"


def test_first_guess_says_so():
    text = estimate.transcribe_time(1200, None)
    assert text.startswith("roughly 7 min") and "first guess" in text
