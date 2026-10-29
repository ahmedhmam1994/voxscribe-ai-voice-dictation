from datetime import datetime

import pytest

from core import meeting_notes
from core.meeting import OTHERS, YOU, Line

STARTED = datetime(2026, 10, 28, 14, 30)


def _lines():
    return [
        Line(0, 20, OTHERS, "Thanks for joining. Maria will send the invoice by Friday. "
             "We decided to move the launch to next week."),
        Line(25, 30, YOU, "Can you share the budget numbers before the review?"),
        Line(32, 40, OTHERS, "I'll update the roadmap tomorrow. The weather was nice."),
        Line(3700, 3710, YOU, "We agreed to keep the current pricing."),
    ]


def test_action_items_have_time_and_speaker():
    items = meeting_notes.action_items(_lines())
    assert "Maria will send the invoice by Friday. (00:00, Others)" in items
    assert "I'll update the roadmap tomorrow. (00:32, Others)" in items
    assert not any("weather" in item for item in items)
    assert not any("Thanks for joining" in item for item in items)


def test_a_request_as_a_question_is_a_question_not_an_action():
    lines = _lines()
    assert not any("budget numbers" in item for item in meeting_notes.action_items(lines))
    assert any("budget numbers" in item for item in meeting_notes.questions(lines))


def test_decisions_are_found():
    items = meeting_notes.decisions(_lines())
    assert "We decided to move the launch to next week. (00:00, Others)" in items
    assert any("keep the current pricing" in item and "1:01:40" in item for item in items)


@pytest.mark.parametrize(
    "sentence",
    ["It will be fine.", "We will see how it goes.", "That should be enough.", "Hello there."],
)
def test_ordinary_sentences_are_not_action_items(sentence):
    assert meeting_notes.action_items([Line(0, 1, YOU, sentence)]) == []


def test_clock_formats():
    assert meeting_notes.clock(5) == "00:05"
    assert meeting_notes.clock(125) == "02:05"
    assert meeting_notes.clock(3725) == "1:02:05"


def test_the_note_has_every_section_in_order():
    note = meeting_notes.build_note(_lines(), STARTED, 3800)
    positions = [
        note.index(heading)
        for heading in ("# Meeting 2026-10-28 14:30", "## Action items", "## Decisions",
                        "## Questions", "## Transcript")
    ]
    assert positions == sorted(positions)
    assert "- [ ] Maria will send the invoice by Friday." in note
    assert "**[00:25] You:** Can you share the budget numbers before the review?" in note
    assert "**Speakers:** You, Others" in note
    assert "duration: 63 min" in note
    assert note.startswith("---\ntags: [meeting]\ndate: 2026-10-28\n")


def test_an_empty_meeting_says_so():
    note = meeting_notes.build_note([], STARTED, 20)
    assert "No speech was recognized" in note
    assert "## Transcript" not in note


def test_a_microphone_only_meeting_is_marked():
    note = meeting_notes.build_note([Line(0, 5, YOU, "Just me.")], STARTED, 60, with_others=False)
    assert "microphone only" in note


def test_no_items_found_is_stated():
    note = meeting_notes.build_note([Line(0, 5, YOU, "Hello everyone.")], STARTED, 60)
    assert note.count("- none found") == 2


def test_save_note_never_overwrites(tmp_path):
    first = meeting_notes.save_note(tmp_path / "sub", "one", STARTED)
    second = meeting_notes.save_note(tmp_path / "sub", "two", STARTED)
    assert first.name == "2026-10-28 14-30 Meeting.md"
    assert second.name == "2026-10-28 14-30 Meeting (2).md"
    assert first.read_text(encoding="utf-8") == "one"


def test_the_words_action_item_alone_are_not_an_item():
    lines = [Line(0, 5, OTHERS, "Action item. Maria will call the client.")]
    assert meeting_notes.action_items(lines) == ["Maria will call the client. (00:00, Others)"]
