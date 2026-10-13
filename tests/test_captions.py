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


def test_tail_cards_are_balanced_not_a_single_word():
    text = "word " * 17 + "last"  # 89 characters, just over two lines of 42
    cards = split_segments([(0.0, 9.0, text.strip())])
    lengths = [len(t.replace("\n", " ")) for _s, _e, t in cards]
    assert len(cards) == 2
    assert min(lengths) >= 30


def test_review_flags_fast_overlap_and_gap():
    from core.captions import review_flags

    cards = [
        (0.0, 0.4, "Quick"),
        (0.3, 4.0, "Starts before the last one ended"),
        (9.0, 12.0, "After a long silence"),
        (12.0, 13.0, "x" * 60),
    ]
    reasons = dict()
    for number, reason in review_flags(cards):
        reasons.setdefault(number, []).append(reason)
    assert "only 0.4s" in reasons[1][0]
    assert any("overlaps" in r for r in reasons[2])
    assert any("silence" in r for r in reasons[3])
    assert any("too fast" in r for r in reasons[4])


def test_clean_cards_have_no_flags():
    from core.captions import review_flags

    assert review_flags([(0.0, 3.0, "A normal caption"), (3.2, 6.0, "And another one")]) == []


def _words(text, start, per_word=0.4, gap_after=None):
    out, t = [], start
    for i, w in enumerate(text.split()):
        out.append((t, t + per_word, w))
        t += per_word
        if gap_after and i in gap_after:
            t += gap_after[i]
    return out


def test_timed_cards_follow_the_words():
    from core.captions import split_segments_timed

    text = "So the first thing you want to do is open the folder, and then you pick every file you want to run."
    words = _words(text, 10.0, 0.3, {11: 2.0})
    cards = split_segments_timed([(10.0, words[-1][1], text, words)], 42)
    assert len(cards) > 1
    assert cards[0][0] == 10.0
    for (_s1, e1, _t1), (s2, _e2, _t2) in zip(cards, cards[1:], strict=False):
        assert e1 <= s2 + 1e-9
    spoken_again = [w for w in words if w[0] > 10 + 12 * 0.3 + 1.5][0][0]
    assert any(abs(s - spoken_again) < 0.05 for s, _e, _t in cards)


def test_timed_card_does_not_hang_through_a_silence():
    from core.captions import split_segments_timed

    first = _words("costs fourteen dollars", 0.0, 0.4)
    last = _words("Thanks.", 8.0, 0.4)
    text = "costs fourteen dollars Thanks."
    cards = split_segments_timed([(0.0, 8.4, text, first + last)], 12)
    assert cards[0][1] < 3.0
    assert cards[-1][0] == 8.0
    assert cards[-1][2] == "Thanks."


def test_timed_cards_last_at_least_a_second_when_there_is_room():
    from core.captions import MIN_CARD_SECONDS, split_segments_timed

    words = _words("Yes.", 5.0, 0.2)
    card = split_segments_timed([(5.0, 5.2, "Yes.", words)], 42)[0]
    assert card[1] - card[0] >= MIN_CARD_SECONDS


def test_timed_split_falls_back_when_words_do_not_match_the_text():
    from core.captions import split_segments_timed

    text = "Speaker 1: " + "word " * 20
    words = _words("word " * 20, 0.0, 0.3)
    cards = split_segments_timed([(0.0, 6.0, text.strip(), words)], 42)
    assert len(cards) >= 2
    assert cards[0][0] == 0.0 and abs(cards[-1][1] - 6.0) < 0.5


def test_timed_zero_turns_it_off():
    from core.captions import split_segments_timed

    words = _words("hi there", 1.0)
    assert split_segments_timed([(1.0, 2.0, "hi there", words)], 0) == [(1.0, 2.0, "hi there")]


def test_review_flags_a_card_that_stays_far_too_long():
    from core.captions import review_flags

    flags = review_flags([(0.0, 9.4, "The new release is out and the upgrade costs fourteen dollars.")])
    assert any("longer than the speech needs" in reason for _n, reason in flags)


def test_timed_split_copes_with_words_that_carry_leading_spaces():
    from core.captions import split_segments_timed

    text = "So the first thing you want to do is open the folder and then you pick every file you want to run overnight."
    words = [(i * 0.3, i * 0.3 + 0.25, " " + w) for i, w in enumerate(text.split())]
    cards = split_segments_timed([(0.0, 8.0, text, words)], 42)
    assert len(cards) > 1
    assert all("  " not in t for _s, _e, t in cards)
    assert max(e - s for s, e, _t in cards) < 7.0


def test_a_very_long_segment_is_cut_into_cards_that_all_fit():
    text = (
        "Well, the first thing we did was write down every service. Then we ranked them by "
        "risk. Great. The new release is version 1.7.2, and the pro upgrade costs $14. Thanks."
    )
    cards = split_segments([(0.0, 18.0, text)], 42)
    assert len(cards) >= 2
    for _s, _e, t in cards:
        assert len(t.split("\n")) <= 2
        assert all(len(line) <= 42 for line in t.split("\n"))


def test_timed_cards_for_a_long_segment_with_pauses_stay_short():
    from core.captions import split_segments_timed

    words = []
    t = 28.2
    for w in "Well, the first thing we did was write down every service.".split():
        words.append((t, t + 0.3, w)); t += 0.3
    t += 1.0
    for w in "Then we ranked them by risk.".split():
        words.append((t, t + 0.3, w)); t += 0.3
    t += 2.0
    for w in "Great. The new release is version 1.7.2, and the pro upgrade costs $14.".split():
        words.append((t, t + 0.3, w)); t += 0.3
    t += 2.7
    words.append((t, t + 0.5, "Thanks."))
    text = " ".join(w[2] for w in words)
    cards = split_segments_timed([(28.2, t + 0.5, text, words)], 42)
    assert max(e - s for s, e, _t in cards) < 7.0
    assert cards[-1][2] == "Thanks."
