"""Tests for core/cleanup.py's regex-based filler-word/spacing cleanup.

Ports the cases from that module's __main__ smoke-test block into real
assertions, plus a few edge cases the smoke test didn't cover.
"""

from core.cleanup import clean_transcript


def test_empty_and_blank_pass_through_unchanged():
    assert clean_transcript("") == ""
    assert clean_transcript("   ") == "   "


def test_strips_simple_fillers():
    assert clean_transcript("um so I was thinking about it") == "So I was thinking about it"
    assert clean_transcript("umm") == ""


def test_strips_repeated_words():
    assert clean_transcript("uh the the meeting is at 3 pm") == "The meeting is at 3 pm"
    assert clean_transcript("I I I need to go") == "I need to go"


def test_keeps_legitimately_repeated_words():
    assert clean_transcript("I had had enough") == "I had had enough"
    assert clean_transcript("bye bye") == "Bye bye"
    assert clean_transcript("it is 50 50") == "It is 50 50"
    assert clean_transcript("no no no") == "No no no"


def test_strips_comma_bounded_like_filler():
    # The comma before "like," is kept -- only ", like," itself collapses
    # to a single ",", not removed entirely.
    assert clean_transcript("it was, like, really loud") == "It was, really loud"


def test_strips_leading_like_after_lead_word():
    assert clean_transcript("So like, I went to the store") == "So I went to the store"


def test_does_not_strip_real_like():
    assert clean_transcript("I like pizza a lot") == "I like pizza a lot"


def test_strips_you_know_filler():
    result = clean_transcript("you know it was really loud in there")
    assert "you know" not in result.lower()
    assert result == "It was really loud in there"


def test_fixes_spacing_around_punctuation():
    # The first letter and the letter after each sentence end are capitalized.
    assert clean_transcript("hello , world .   this  is   a test") == "Hello, world. This is a test"


def test_capitalizes_first_letter():
    assert clean_transcript("hello world") == "Hello world"


def test_no_stray_leading_punctuation_after_stripped_filler():
    result = clean_transcript("um, so I left")
    assert not result.startswith((",", ";", ":"))


def test_capitalizes_after_each_sentence_end():
    assert clean_transcript("hello there. how are you? i am fine! see you") == (
        "Hello there. How are you? I am fine! See you"
    )


def test_does_not_capitalize_after_abbreviations():
    assert clean_transcript("use a tool, e.g. the hammer") == "Use a tool, e.g. the hammer"
    assert clean_transcript("bring pens, etc. and paper") == "Bring pens, etc. and paper"
