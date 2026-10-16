import json

import pytest

from core.word_lists import FORMAT, export_text, merge_replacements, parse_import


def test_an_export_reads_back_the_same():
    vocabulary = ["VoxScribe", "faster-whisper"]
    pairs = [("vox scribe", "VoxScribe"), ("um", ""), ("c sharp", "C#")]
    assert parse_import(export_text(vocabulary, pairs)) == (vocabulary, pairs)


def test_the_export_is_readable_json_with_the_format_name():
    data = json.loads(export_text(["Ahmed"], [("a med", "Ahmed")]))
    assert data["format"] == FORMAT
    assert data["version"] == 1
    assert data["replacements"] == [{"heard": "a med", "replacement": "Ahmed"}]


def test_names_with_accents_stay_as_written():
    assert "Zoë" in export_text(["Zoë"], [])


def test_blank_entries_are_left_out_of_the_export():
    data = json.loads(export_text(["", "  ", "Sam"], [("", "x"), ("a", "b")]))
    assert data["vocabulary"] == ["Sam"]
    assert data["replacements"] == [{"heard": "a", "replacement": "b"}]


def test_plain_heard_replacement_lines_import_too():
    assert parse_import("vox scribe => VoxScribe\nnot a rule\num =>\n") == (
        [],
        [("vox scribe", "VoxScribe"), ("um", "")],
    )


def test_a_byte_order_mark_from_notepad_is_ignored():
    assert parse_import("﻿vox scribe => VoxScribe") == ([], [("vox scribe", "VoxScribe")])


def test_a_vocabulary_term_with_a_comma_splits_like_the_settings_box():
    text = json.dumps({"format": FORMAT, "version": 1, "vocabulary": ["Sam, Tom"]})
    assert parse_import(text) == (["Sam", "Tom"], [])


def test_broken_entries_are_skipped():
    text = json.dumps(
        {
            "format": FORMAT,
            "version": 1,
            "vocabulary": ["Sam", 3, None],
            "replacements": [
                {"heard": "a", "replacement": "b"},
                {"heard": ""},
                "junk",
                {"heard": "x"},
            ],
        }
    )
    assert parse_import(text) == (["Sam"], [("a", "b"), ("x", "")])


@pytest.mark.parametrize(
    "text",
    ["", "hello there", "{not json", json.dumps({"format": "something-else"}), "[1, 2]"],
)
def test_a_file_that_is_not_a_word_list_is_refused(text):
    with pytest.raises(ValueError):
        parse_import(text)


def test_merging_adds_new_rules_at_the_end():
    merged, added, changed = merge_replacements([("a", "b")], [("c", "d")])
    assert merged == [("a", "b"), ("c", "d")]
    assert (added, changed) == (1, 0)


def test_a_rule_for_the_same_words_is_changed_in_place():
    merged, added, changed = merge_replacements(
        [("Vox Scribe", "Voxscribe"), ("x", "y")], [("vox scribe", "VoxScribe")]
    )
    assert merged == [("vox scribe", "VoxScribe"), ("x", "y")]
    assert (added, changed) == (0, 1)


def test_importing_the_same_list_twice_changes_nothing():
    pairs = [("a", "b"), ("c", "d")]
    merged, added, changed = merge_replacements(pairs, pairs)
    assert merged == pairs
    assert (added, changed) == (0, 0)


def test_repeats_inside_the_file_do_not_add_twice():
    merged, added, _ = merge_replacements([], [("a", "b"), ("A", "c")])
    assert merged == [("A", "c")]
    assert added == 1
