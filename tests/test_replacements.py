"""Tests for core/replacements.py's word replacement logic."""

from core import replacements
from core.replacements import (
    add_replacement,
    add_rule,
    apply_replacements,
    clean_selection,
    parse_replacements_text,
)


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


# --- fixing a word from the transcript --------------------------------------


def test_clean_selection_drops_punctuation_and_squeezes_spaces():
    assert clean_selection("  whisker,  ") == "whisker"
    assert clean_selection('"Hello there."') == "Hello there"
    assert clean_selection("vox\n  scribe") == "vox scribe"
    assert clean_selection("...") == ""
    assert clean_selection("don't") == "don't"
    assert clean_selection("well-known,") == "well-known"


def test_add_rule_adds_below_the_rules_already_there():
    pairs = [("vox scribe", "VoxScribe")]
    assert add_rule(pairs, "noon,", "one") == (
        [("vox scribe", "VoxScribe"), ("noon", "one")],
        "added",
    )
    assert pairs == [("vox scribe", "VoxScribe")]  # the list passed in is not changed


def test_add_rule_updates_a_rule_for_the_same_words_in_place():
    pairs = [("a", "b"), ("Noon", "one"), ("c", "d")]
    assert add_rule(pairs, "noon", "two") == (
        [("a", "b"), ("noon", "two"), ("c", "d")],
        "updated",
    )


def test_add_rule_same_rule_again_changes_nothing():
    pairs = [("noon", "one")]
    assert add_rule(pairs, "Noon", "one") == (pairs, "unchanged")


def test_add_rule_refuses_empty_or_identical_corrections():
    pairs = [("x", "y")]
    assert add_rule(pairs, "noon", "   ") == (pairs, "invalid")
    assert add_rule(pairs, "  ", "one") == (pairs, "invalid")
    assert add_rule(pairs, "noon", "noon") == (pairs, "invalid")


def test_add_rule_turns_a_line_break_in_the_answer_into_a_space():
    assert add_rule([], "a b", "c\nd") == ([("a b", "c d")], "added")


def test_add_replacement_saves_only_when_something_changed(monkeypatch):
    saved = []
    store = [("keep", "me")]
    monkeypatch.setattr(replacements, "get_replacements", lambda: list(store))
    monkeypatch.setattr(replacements, "set_replacements", saved.append)

    assert add_replacement("noon", "one") == "added"
    assert saved == [[("keep", "me"), ("noon", "one")]]

    assert add_replacement("keep", "me") == "unchanged"
    assert add_replacement("noon", "noon") == "invalid"
    assert len(saved) == 1
