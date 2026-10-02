"""Tests for core/replacements.py's word replacement logic."""

from core.replacements import apply_replacements, parse_replacements_text


def test_parse_skips_bad_lines_and_allows_empty_replacement():
    text = "vox scribe => VoxScribe\nno arrow here\n => nothing\nuh huh =>\n"
    assert parse_replacements_text(text) == [("vox scribe", "VoxScribe"), ("uh huh", "")]


def test_whole_word_case_insensitive():
    pairs = [("vox scribe", "VoxScribe")]
    assert apply_replacements("I use Vox Scribe daily.", pairs) == "I use VoxScribe daily."


def test_does_not_replace_inside_longer_words():
    pairs = [("cat", "dog")]
    assert apply_replacements("concatenate the cat", pairs) == "concatenate the dog"


def test_empty_replacement_deletes_word_and_tidies_spacing():
    pairs = [("basically", "")]
    assert apply_replacements("It is basically done, basically.", pairs) == "It is done,."


def test_replacement_text_is_literal_not_regex():
    pairs = [("path", r"C:\new\1")]
    assert apply_replacements("the path here", pairs) == r"the C:\new\1 here"


def test_no_pairs_returns_text_unchanged():
    assert apply_replacements("hello world", []) == "hello world"


def test_empty_text():
    assert apply_replacements("", [("a", "b")]) == ""
