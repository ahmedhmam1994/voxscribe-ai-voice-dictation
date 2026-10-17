"""Tests for core/voice_commands.py's spoken punctuation/formatting commands."""

from core.voice_commands import (
    apply_replace,
    apply_trailing_replace,
    apply_transform,
    apply_voice_commands,
    compute_deletion,
    compute_rewrite,
    get_editing_command,
    get_replace_command,
    get_transform_command,
    is_send_command,
    split_trailing_send,
    split_trailing_transform,
    is_undo_command,
)


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


def test_is_undo_command_recognizes_whole_utterance_phrases():
    assert is_undo_command("scratch that")
    assert is_undo_command("Scratch that.")
    assert is_undo_command("undo that")
    assert is_undo_command("delete that")
    assert is_undo_command("undo")
    assert is_undo_command("UNDO THAT")


def test_is_undo_command_rejects_embedded_or_different_text():
    assert not is_undo_command("scratch that itch")
    assert not is_undo_command("please undo that email")
    assert not is_undo_command("hello world")


def test_get_editing_command_recognizes_word_and_sentence_phrases():
    assert get_editing_command("delete last word") == "word"
    assert get_editing_command("Delete that word.") == "word"
    assert get_editing_command("scratch that word") == "word"
    assert get_editing_command("delete last sentence") == "sentence"
    assert get_editing_command("delete that sentence") == "sentence"
    assert get_editing_command("scratch that sentence") == "sentence"
    assert get_editing_command("scratch that") == "all"
    assert get_editing_command("hello world") is None
    assert get_editing_command("") is None


def test_compute_deletion_all_clears_everything():
    assert compute_deletion("hello there", "all") == ("", 11)
    assert compute_deletion("", "all") == ("", 0)


def test_compute_deletion_word_removes_last_word_and_its_space():
    assert compute_deletion("hello there friend", "word") == ("hello there", 7)
    assert compute_deletion("hello", "word") == ("", 5)
    assert compute_deletion("hello there ", "word") == ("hello", 7)


def test_compute_deletion_sentence_removes_last_sentence_only():
    assert compute_deletion("First one. Second one.", "sentence") == ("First one.", 12)
    assert compute_deletion("Just one sentence.", "sentence") == ("", 18)
    assert compute_deletion("No terminators here", "sentence") == ("", 19)
    assert not is_undo_command("")


# --- capitalize / upper / lower ---------------------------------------------


def test_transform_commands_are_whole_utterances_only():
    assert get_transform_command("Capitalize that.") == "capitalize"
    assert get_transform_command("capitalise that") == "capitalize"
    assert get_transform_command("All caps") == "uppercase"
    assert get_transform_command("Make that uppercase.") == "uppercase"
    assert get_transform_command("lowercase that") == "lowercase"
    assert get_transform_command("All lowercase!") == "lowercase"
    assert get_transform_command("please capitalize that word in the title") is None
    assert get_transform_command("the sign said all caps and bold") is None
    assert get_transform_command("") is None


def test_capitalize_starts_every_word_and_keeps_spacing():
    assert apply_transform("bring the notes", "capitalize") == "Bring The Notes"
    assert apply_transform("a  b\nc", "capitalize") == "A  B\nC"
    assert apply_transform("Already capital", "capitalize") == "Already Capital"


def test_upper_and_lower_change_the_whole_text():
    assert apply_transform("Hello, world.", "uppercase") == "HELLO, WORLD."
    assert apply_transform("Hello, World.", "lowercase") == "hello, world."


# --- replace X with Y --------------------------------------------------------


def test_replace_command_splits_into_the_two_phrases():
    assert get_replace_command("Replace Sam with Tom.") == ("Sam", "Tom")
    assert get_replace_command("replace the battery with a new one") == (
        "the battery",
        "a new one",
    )


def test_replace_command_needs_both_sides():
    assert get_replace_command("please replace it") is None
    assert get_replace_command("replace with") is None
    assert get_replace_command("replace sam with") is None
    assert get_replace_command("") is None


def test_replace_only_touches_whole_words_and_ignores_case():
    assert apply_replace("Meet me at noon", "noon", "one") == "Meet me at one"
    assert apply_replace("Meet me at Noon.", "NOON", "one") == "Meet me at one."
    assert apply_replace("noonish plans", "noon", "one") is None
    assert apply_replace("Meet me at noon", "midnight", "one") is None


def test_replace_changes_every_occurrence_and_keeps_symbols_as_typed():
    assert apply_replace("coffee and coffee", "coffee", "tea") == "tea and tea"
    assert apply_replace("the price is cheap", "cheap", r"$5 \1 done") == r"the price is $5 \1 done"


# --- send it -----------------------------------------------------------------


def test_send_it_is_only_a_whole_utterance():
    assert is_send_command("Send it.")
    assert is_send_command("press enter")
    assert is_send_command("Hit enter!")
    assert not is_send_command("send it to Sam")
    assert not is_send_command("don't send it yet")
    assert not is_send_command("")


# --- the fewest keystrokes ---------------------------------------------------


def test_rewrite_keeps_the_shared_start():
    assert compute_rewrite("meet me at noon", "meet me at one") == (4, "one")
    assert compute_rewrite("bring the notes", "BRING THE NOTES") == (15, "BRING THE NOTES")
    assert compute_rewrite("same", "same") == (0, "")
    assert compute_rewrite("abc", "abcdef") == (0, "def")
    assert compute_rewrite("abcdef", "abc") == (3, "")


# --- a command at the end of the same sentence -------------------------------


def test_a_command_after_a_pause_ends_the_sentence():
    assert split_trailing_transform("Bring the notes, all caps.") == (
        "Bring the notes",
        "uppercase",
    )
    assert split_trailing_transform("bring the notes. Capitalize that") == (
        "bring the notes",
        "capitalize",
    )
    assert split_trailing_transform("SHOUTING, all lowercase!") == ("SHOUTING", "lowercase")


def test_the_clear_phrases_count_even_without_a_pause():
    assert split_trailing_transform("bring the notes uppercase that") == (
        "bring the notes",
        "uppercase",
    )
    assert split_trailing_transform("meet me at noon capitalize that.") == (
        "meet me at noon",
        "capitalize",
    )


def test_the_bare_phrases_need_a_pause_so_ordinary_words_are_safe():
    assert split_trailing_transform("write the title in all caps") is None
    assert split_trailing_transform("she typed it all lowercase") is None
    assert split_trailing_transform("all caps") is None
    assert split_trailing_transform(", all caps") is None
    assert split_trailing_transform("capitalize that word, please") is None


def test_the_models_usual_mishearings_count_too():
    assert split_trailing_transform("Meet me at noon. Capitalize Z.") == (
        "Meet me at noon",
        "capitalize",
    )
    assert split_trailing_transform("With me, I had now capitalized that") == (
        "With me, I had now",
        "capitalize",
    )
    assert get_transform_command("Capitalise Z.") == "capitalize"


def test_a_question_or_exclamation_mark_stays_with_the_sentence():
    assert split_trailing_transform("Do you hear me? All caps!") == (
        "Do you hear me?",
        "uppercase",
    )
    assert split_trailing_transform("Stop! Lowercase that.") == ("Stop!", "lowercase")


def test_a_bare_keyword_needs_a_pause_and_is_never_mid_sentence():
    assert split_trailing_transform("bring the notes, uppercase") == (
        "bring the notes",
        "uppercase",
    )
    assert split_trailing_transform("we should capitalize") is None
    assert split_trailing_transform("we should capitalize on this chance") is None


def test_a_trailing_replace_changes_the_sentence_before_it():
    assert apply_trailing_replace("Meet me at noon. Replace noon with one.") == "Meet me at one"
    assert apply_trailing_replace("meet me at noon, replace noon with one") == "meet me at one"
    assert apply_trailing_replace("Where is Sam? Replace Sam with Tom.") == "Where is Tom?"


def test_a_trailing_replace_needs_the_phrase_to_be_in_the_sentence():
    assert apply_trailing_replace("I will replace the battery with a new one") is None
    assert apply_trailing_replace("Please, replace the filter with a new one") is None
    assert apply_trailing_replace("Meet me at noon. Replace lunch with one.") is None
    assert apply_trailing_replace("Replace noon with one") is None
    assert apply_trailing_replace("Meet me at noon, replace noon with") is None


def test_an_it_command_needs_a_pause_so_ordinary_sentences_are_safe():
    assert split_trailing_transform("We need to capitalize it.") is None
    assert split_trailing_transform("you can lowercase it") is None
    assert split_trailing_transform("Here is the title, capitalize it.") == (
        "Here is the title",
        "capitalize",
    )


def test_send_it_at_the_end_of_a_message_after_a_pause():
    assert (
        split_trailing_send("Send me a DM after you wake up tomorrow, send it")
        == "Send me a DM after you wake up tomorrow"
    )
    assert split_trailing_send("How are you? Send it.") == "How are you?"
    assert split_trailing_send("Sounds good. Press enter") == "Sounds good"


def test_send_it_at_the_end_counts_without_a_pause_too():
    # What the speech model actually wrote in testing: no comma.
    assert split_trailing_send("You tomorrow at noon send it") == "You tomorrow at noon"
    assert split_trailing_send("See you tomorrow at noon send it.") == "See you tomorrow at noon"
    assert split_trailing_send("Done hit enter") == "Done"


def test_send_it_that_is_part_of_the_sentence_is_typed():
    assert split_trailing_send("please send it to Sam") is None
    assert split_trailing_send("I will send it") is None
    assert split_trailing_send("Don't send it.") is None
    assert split_trailing_send("Remember to send it") is None
    assert split_trailing_send("Can you send it") is None
    assert split_trailing_send("Please send it") is None
    assert split_trailing_send("Let me send that") is None
    assert split_trailing_send("Send it.") is None
    assert split_trailing_send(", send it") is None
