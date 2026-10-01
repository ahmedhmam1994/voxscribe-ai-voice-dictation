"""Tests for core/srt.py's SRT caption formatting."""

from core.srt import format_srt


def test_empty_segments_gives_empty_string():
    assert format_srt([]) == ""


def test_single_segment_format():
    srt = format_srt([(0.0, 2.5, "Hello world")])
    assert srt == "1\n00:00:00,000 --> 00:00:02,500\nHello world\n"


def test_multiple_segments_are_numbered_in_order():
    srt = format_srt(
        [
            (0.0, 1.0, "First"),
            (1.5, 3.25, "Second"),
        ]
    )
    assert srt == (
        "1\n00:00:00,000 --> 00:00:01,000\nFirst\n"
        "\n"
        "2\n00:00:01,500 --> 00:00:03,250\nSecond\n"
    )


def test_blank_text_segments_are_skipped_and_do_not_break_numbering():
    srt = format_srt(
        [
            (0.0, 1.0, "First"),
            (1.0, 1.1, "   "),
            (1.5, 3.0, "Second"),
        ]
    )
    assert "1\n" in srt
    assert srt.count("-->") == 2
    assert "First" in srt and "Second" in srt


def test_timestamp_rolls_over_hours_and_minutes():
    srt = format_srt([(3661.234, 3662.0, "Later")])
    assert "01:01:01,234 --> 01:01:02,000" in srt
