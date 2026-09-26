"""Tests for core/voice_commands.py's spoken punctuation/formatting commands."""

from core.voice_commands import apply_voice_commands


def test_empty_and_blank_pass_through_unchanged():
    assert apply_voice_commands("") == ""
    assert apply_voice_commands("   ") == "   "


def test_no_commands_passes_through_unchanged():
    assert apply_voice_commands("no commands here at all") == "no commands here at all"


def test_period_and_comma():
    assert apply_voice_commands("hello comma world period") == "hello, world."


def test_capitalizes_after_end_of_sentence_command():
    assert apply_voice_commands("hello period the next word") == "hello. The next word"


def test_question_mark_and_exclamation():
    assert apply_voice_commands("what time is it question mark") == "what time is it?"
    assert apply_voice_commands("call me maybe exclamation point") == "call me maybe!"
    assert apply_voice_commands("call me maybe exclamation mark") == "call me maybe!"


def test_full_stop_is_an_alias_for_period():
    assert apply_voice_commands("that is all full stop") == "that is all."


def test_colon_and_semicolon():
    result = apply_voice_commands("item one colon apples comma oranges semicolon and pears")
    assert result == "item one: apples, oranges; and pears"


def test_new_line_and_new_paragraph():
    assert apply_voice_commands("hello new line world") == "hello\nWorld"
    assert apply_voice_commands("hello new paragraph world") == "hello\n\nWorld"


def test_quotes():
    result = apply_voice_commands("she said open quote hello close quote and left")
    assert result == 'she said "hello" and left'


def test_parentheses_and_their_long_forms():
    assert (
        apply_voice_commands("call me open paren maybe close paren today")
        == "call me (maybe) today"
    )
    assert (
        apply_voice_commands("call me open parenthesis maybe close parenthesis today")
        == "call me (maybe) today"
    )


def test_is_case_insensitive():
    assert apply_voice_commands("hello COMMA world PERIOD") == "hello, world."


def test_no_leftover_capitalization_marker():
    assert "\x00" not in apply_voice_commands("hello period world period new line done")
