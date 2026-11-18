from datetime import datetime

import pytest

from core import ask_library, assistant
from core.library import KIND_DICTATION, KIND_MEETING, Item

# A Sunday, so "this week" started six days earlier, on Monday 9 Nov.
NOW = datetime(2026, 11, 15, 18, 0)


def _item(text: str, when: datetime, kind: str = KIND_DICTATION, label: str = "Dictation") -> Item:
    return Item(
        id=f"x|{when.isoformat()}|{text[:10]}",
        kind=kind,
        label=label,
        title=text[:80],
        text=text,
        created=when,
    )


@pytest.mark.parametrize(
    ("question", "start", "end"),
    [
        ("what did I say today", datetime(2026, 11, 15), None),
        ("what did I say yesterday", datetime(2026, 11, 14), datetime(2026, 11, 15)),
        ("what did I tell John last week", datetime(2026, 11, 2), datetime(2026, 11, 9)),
        ("anything about rent this week", datetime(2026, 11, 9), None),
        ("what did the doctor say on Monday", datetime(2026, 11, 9), datetime(2026, 11, 10)),
        ("what did I note on Sunday", datetime(2026, 11, 15), datetime(2026, 11, 16)),
        ("what did I say three days ago", datetime(2026, 11, 12), datetime(2026, 11, 13)),
        ("what did I plan last month", datetime(2026, 10, 1), datetime(2026, 11, 1)),
        ("what is the wifi password", None, None),
    ],
)
def test_time_window(question, start, end):
    window = ask_library.time_window(question, NOW)
    assert (window.start, window.end) == (start, end)


def test_keywords_drop_question_words_and_dates():
    assert ask_library.keywords("What did I tell John about the budget last week?") == [
        "john",
        "budget",
    ]
    assert ask_library.keywords("what did the doctor say on Monday") == ["doctor"]
    assert ask_library.keywords("John's budget, budget") == ["john", "budget"]


def test_finds_the_matching_dictation_and_skips_the_rest():
    items = [
        _item("Told John the budget for Q1 is 40,000 dollars", datetime(2026, 11, 4, 10)),
        _item("Buy milk and eggs", datetime(2026, 11, 4, 11)),
        _item("Budget review moved to Friday", datetime(2026, 10, 1, 9)),
    ]
    sources, window = ask_library.find_sources(
        items, "what did I tell John about the budget last week", NOW
    )
    assert window.label == "last week"
    assert [s.item.text for s in sources] == ["Told John the budget for Q1 is 40,000 dollars"]


def test_rare_words_rank_first():
    items = [
        _item("meeting notes about the office move", datetime(2026, 11, 10)),
        _item("meeting with Priya about the office lease", datetime(2026, 11, 11)),
        _item("meeting again tomorrow", datetime(2026, 11, 12)),
    ]
    sources, _ = ask_library.find_sources(items, "what did Priya say about the meeting", NOW)
    assert sources[0].item.text.startswith("meeting with Priya")


def test_plural_and_ing_forms_match():
    items = [_item("Three budgets were approved at the meetings", datetime(2026, 11, 10))]
    sources, _ = ask_library.find_sources(items, "budget meeting", NOW)
    assert len(sources) == 1


def test_nothing_found_means_no_sources():
    items = [_item("Buy milk", datetime(2026, 11, 14))]
    sources, _ = ask_library.find_sources(items, "what did I tell John about the budget", NOW)
    assert sources == []


def test_a_bare_date_question_takes_that_day_newest_first():
    items = [
        _item("first thing yesterday", datetime(2026, 11, 14, 8)),
        _item("later yesterday", datetime(2026, 11, 14, 16)),
        _item("today", datetime(2026, 11, 15, 9)),
    ]
    sources, _ = ask_library.find_sources(items, "what did I say yesterday", NOW)
    assert [s.item.text for s in sources] == ["later yesterday", "first thing yesterday"]


def test_a_question_with_no_words_and_no_date_finds_nothing():
    items = [_item("hello there", datetime(2026, 11, 14))]
    assert ask_library.find_sources(items, "what did I say?", NOW)[0] == []


def test_long_notes_are_cut_around_the_matching_words():
    filler = " ".join(["filler"] * 600)
    text = f"{filler} the contract with Acme renews in March {filler}"
    items = [_item(text, datetime(2026, 11, 10), KIND_MEETING, "Meeting")]
    sources, _ = ask_library.find_sources(items, "Acme contract", NOW)
    excerpt = sources[0].excerpt
    assert "Acme" in excerpt
    assert len(excerpt) <= ask_library._EXCERPT_CHARS + 6


def test_sources_fit_the_prompt_budget():
    items = [_item(f"budget item {n} " + "x" * 800, datetime(2026, 11, 10)) for n in range(20)]
    sources, _ = ask_library.find_sources(items, "budget", NOW)
    assert 0 < len(sources) <= ask_library.MAX_SOURCES
    assert sum(len(s.excerpt) for s in sources) <= ask_library.SOURCE_BUDGET_CHARS


def test_prompt_numbers_the_notes_with_dates():
    items = [_item("Told John 40,000", datetime(2026, 11, 9, 15, 5))]
    sources, _ = ask_library.find_sources(items, "John", NOW)
    messages = ask_library.build_messages("What did I tell John?", sources, NOW)
    user = messages[1]["content"]
    assert "[1] Dictation, Mon 9 Nov 2026, 3:05 PM:" in user
    assert "Told John 40,000" in user
    assert user.startswith("Today is Sun 15 Nov 2026.")
    assert ask_library.NOT_FOUND in messages[0]["content"]


@pytest.mark.parametrize(
    ("reply", "answer"),
    [
        ("NOT_FOUND", None),
        ("  not found ", None),
        ("<think>hmm</think>On Monday you told John 40,000.", "On Monday you told John 40,000."),
        ('"You said Friday."', "You said Friday."),
        ("", None),
    ],
)
def test_read_answer(reply, answer):
    assert ask_library.read_answer(reply) == answer


# -- the assistant's edit of selected text -------------------------------------


def test_edit_prompt_has_the_instruction_and_the_selection():
    messages = assistant.build_edit_messages("Hello there", "  translate this to Spanish ")
    assert messages[0]["content"] == assistant.EDIT_SYSTEM_PROMPT
    assert messages[1]["content"] == (
        "Instruction: translate this to Spanish\n\nSelected text:\nHello there"
    )


def test_edit_keeps_numbers_for_ordinary_changes():
    original = "Take 5 mg at 8 am"
    assert assistant.check_edit(original, "make this formal", "Please take 5 mg at 8 am.") is None
    assert assistant.check_edit(original, "make this shorter", "Take 5 mg in the morning.")


def test_a_number_written_as_a_word_in_the_reply_still_counts():
    original = "the installer still has 2 bugs"
    assert assistant.check_edit(original, "make this formal", "The installer has two bugs.") is None
    assert assistant.missing_numbers(original, "The installer has bugs.") == ["2"]


def test_number_words_in_the_original_are_not_required():
    assert assistant.check_edit("no one came", "make this formal", "Nobody attended.") is None


def test_a_reply_may_leave_the_selection_numbers_out():
    original = "Can you meet on the 12th at 3?"
    assert assistant.check_edit(original, "reply saying Thursday works", "Thursday works.") is None


def test_edit_rejects_empty_placeholder_and_runaway_replies():
    assert assistant.check_edit("hi", "make this formal", "  ")
    assert assistant.check_edit("hi", "reply yes", "Yes. [Your Name]")
    assert assistant.check_edit("hi", "make this formal", "x" * 2000)


def test_a_too_long_selection_is_refused_before_the_model():
    worker = assistant.Assistant()
    with pytest.raises(assistant.AssistantError):
        worker.edit("x" * (assistant.MAX_SELECTION_CHARS + 1), "make this shorter")
