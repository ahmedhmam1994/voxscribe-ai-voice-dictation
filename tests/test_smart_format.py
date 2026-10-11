"""Tests for core/smart_format.py: spoken emails, web addresses and numbers."""

import pytest

from core.smart_format import parse_number_words, smart_format


@pytest.mark.parametrize(
    ("spoken", "written"),
    [
        ("john dot smith at gmail dot com", "john.smith@gmail.com"),
        ("email me at sam underscore dev at acme dot io please", "email me at sam_dev@acme.io please"),
        ("send it to Anna at work dot org.", "send it to anna@work.org."),
    ],
)
def test_emails(spoken, written):
    assert smart_format(spoken) == written


def test_an_ordinary_word_before_at_is_not_an_email():
    assert smart_format("look at example dot com") == "look at example.com"


@pytest.mark.parametrize(
    ("spoken", "written"),
    [
        ("example dot com", "example.com"),
        ("example dot com slash pricing", "example.com/pricing"),
        ("w w w dot example dot org", "www.example.org"),
        ("https colon slash slash my dash site dot dev slash docs", "https://my-site.dev/docs"),
    ],
)
def test_web_addresses(spoken, written):
    assert smart_format(spoken) == written


@pytest.mark.parametrize(
    ("spoken", "written"),
    [
        ("twenty five percent", "25%"),
        ("one hundred and five dollars", "$105"),
        ("two thousand twenty six", "2026"),
        ("three point five", "3.5"),
        ("five percent", "5%"),
        ("a total of forty two items", "a total of 42 items"),
        ("eleven", "11"),
    ],
)
def test_numbers(spoken, written):
    assert smart_format(spoken) == written


def test_a_lone_small_number_stays_a_word():
    assert smart_format("one of them and two more") == "one of them and two more"


def test_a_phrase_that_does_not_parse_is_left_alone():
    assert smart_format("twenty twenty six") == "twenty twenty six"


def test_a_run_of_spoken_digits_becomes_a_phone_number():
    assert smart_format("call five five five one two three four now") == "call 5551234 now"


def test_plain_text_and_empty_text_are_unchanged():
    assert smart_format("Hello there, how are you?") == "Hello there, how are you?"
    assert smart_format("") == ""


@pytest.mark.parametrize(
    ("phrase", "value"),
    [("one hundred twenty three", 123), ("nine hundred ninety nine", 999), ("one million", 1_000_000)],
)
def test_parse_number_words(phrase, value):
    assert parse_number_words(phrase) == value
