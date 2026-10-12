"""Tests for core/captions.py's caption splitting."""

from core.captions import split_segments
from core.srt import format_srt

LONG = (
    "So the first thing you want to do is open the folder, and then you pick every "
    "file you want to run. After that it works through them one at a time."
)


def test_short_segment_is_untouched():
    assert split_segments([(0.0, 2.0, "Hello there")]) == [(0.0, 2.0, "Hello there")]


def test_long_segment_becomes_cards_within_two_lines_of_42():
    cards = split_segments([(0.0, 10.0, LONG)])
    assert len(cards) > 1
    for _start, _end, text in cards:
        lines = text.split("\n")
        assert len(lines) <= 2
        assert all(len(line) <= 42 for line in lines)


def test_no_words_are_lost_or_reordered():
    cards = split_segments([(0.0, 10.0, LONG)])
    assert " ".join(t.replace("\n", " ") for _s, _e, t in cards) == LONG


def test_times_stay_inside_the_segment_and_do_not_overlap():
    cards = split_segments([(4.0, 14.0, LONG)])
    assert cards[0][0] == 4.0
    assert abs(cards[-1][1] - 14.0) < 1e-9
    for (_s1, e1, _t1), (s2, _e2, _t2) in zip(cards, cards[1:], strict=False):
        assert abs(e1 - s2) < 1e-9


def test_prefers_to_cut_at_a_sentence_end():
    text = "I opened the folder and looked around. Then I picked every single file there and ran them"
    cards = split_segments([(0.0, 8.0, text)])
    assert cards[0][2].replace("\n", " ").endswith("around.")


def test_two_line_card_is_balanced():
    text = split_segments([(0.0, 3.0, "this is a caption that needs two lines to read")])[0][2]
    first, second = text.split("\n")
    assert abs(len(first) - len(second)) < 12


def test_zero_turns_it_off():
    assert split_segments([(0.0, 5.0, LONG)], 0) == [(0.0, 5.0, LONG)]


def test_a_very_long_word_does_not_loop_forever():
    cards = split_segments([(0.0, 1.0, "x" * 200)])
    assert "".join(t.replace("\n", "") for _s, _e, t in cards) == "x" * 200


def test_blank_segments_are_dropped_and_srt_renders():
    cards = split_segments([(0.0, 1.0, "   "), (1.0, 5.0, LONG)])
    assert format_srt(cards).startswith("1\n00:00:01,000 -->")
