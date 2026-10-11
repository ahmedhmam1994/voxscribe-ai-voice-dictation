"""Tests for core/code_dictation.py: spoken identifiers and symbols to code."""

import pytest

from core.code_dictation import to_code


@pytest.mark.parametrize(
    ("spoken", "expected"),
    [
        ("camel case user name", "userName"),
        ("pascal case user name", "UserName"),
        ("snake case user name", "user_name"),
        ("upper snake case max retry count", "MAX_RETRY_COUNT"),
        ("constant case api key", "API_KEY"),
        ("kebab case main header", "main-header"),
        ("dot case app config", "app.config"),
    ],
)
def test_case_styles(spoken, expected):
    assert to_code(spoken) == expected


def test_a_case_command_stops_at_the_next_symbol():
    assert to_code("camel case get user open paren id close paren") == "getUser(id)"


def test_assignment_gets_spaces_around_equals():
    assert to_code("snake case total count equals zero") == "total_count = zero"


def test_two_identifiers_in_one_line():
    assert (
        to_code("camel case user name equals camel case first name")
        == "userName = firstName"
    )


def test_brackets_attach_to_their_contents():
    assert to_code("open bracket one comma two close bracket") == "[one, two]"


def test_words_with_no_case_command_are_kept():
    assert to_code("return value") == "return value"


def test_a_new_line_breaks_the_line():
    assert to_code("import os new line import sys") == "import os\nimport sys"


def test_longer_phrase_wins_over_a_shorter_one():
    assert to_code("a double equals b") == "a == b"


def test_dot_joins_a_member_access():
    assert to_code("self dot snake case user id") == "self.user_id"


def test_punctuation_in_the_transcript_is_ignored():
    assert to_code("Camel case, user name.") == "userName"


def test_empty_input_gives_empty_output():
    assert to_code("") == ""
