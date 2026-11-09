"""core/short_forms.py: the mishearings came from running spoken short forms
through Parakeet and Whisper."""

import pytest

from core.short_forms import apply_short_forms


@pytest.mark.parametrize(
    ("heard", "typed"),
    [
        # ASAP said as a word.
        ("Call me tomorrow ISAP", "Call me tomorrow ASAP"),
        ("Call me tomorrow ISAP.", "Call me tomorrow ASAP."),
        ("Call me tomorrow Isep.", "Call me tomorrow ASAP."),
        ("Call me tomorrow Isab", "Call me tomorrow ASAP"),
        ("send it asap please", "send it ASAP please"),
        # Other misheard ones.
        ("I decay what he wants.", "IDK what he wants."),
        ("Bring pens, paper, eat etc.", "Bring pens, paper, etc."),
        ("bring pins, paper, et cetera.", "bring pins, paper, etc."),
        ("apples, et cetera, and pears", "apples, etc., and pears"),
        ("I am 000 until Friday", "I am OOO until Friday"),
        # Lowercase from the model.
        ("oh and btw, I am late", "oh and BTW, I am late"),
        ("fyi the office is closed", "FYI the office is closed"),
        ("tbh I liked it, imo it is long", "TBH I liked it, IMO it is long"),
        # Spelled with gaps or dots.
        ("B T W, the meeting moved", "BTW, the meeting moved"),
        ("F.Y.I., the office is closed.", "FYI, the office is closed."),
        ("I will send it by E.O.D.", "I will send it by EOD."),
        ("I will send it by E.O.D. Then I leave.", "I will send it by EOD. Then I leave."),
        ("send me a d m", "send me a DM"),
        # etc gets its full stop.
        ("apples, oranges, etc", "apples, oranges, etc."),
        ("apples, oranges, etc.", "apples, oranges, etc."),
    ],
)
def test_short_forms(heard, typed):
    assert apply_short_forms(heard) == typed


@pytest.mark.parametrize(
    "text",
    [
        "",
        "Please send it ASAP.",
        "What is your ETA?",
        "That was funny lol.",
        "The eta of the Greek alphabet.",
        "I decay slowly over time.",
        "She paid 1,000 dollars.",
        "I am oh so tired.",
        "We eat at noon.",
        "I'm a big fan of the A team.",
        "Section 5 B, paragraph 2.",
    ],
)
def test_ordinary_text_is_left_alone(text):
    assert apply_short_forms(text) == text
