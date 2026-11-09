"""Chat short forms (ASAP, BTW, FYI, etc.) written the way people type them.

Speech models know these when the letters are spelled out ("B T W"), but a
short form said as a word comes out as whatever it sounds like: ASAP said
"ay-sap" was typed as "ISAP", "Isep" or "Isab"; IDK as "I decay"; et cetera
as "eat etc."; out of office as "000". These are the mishearings found by
running spoken short forms through Parakeet and Whisper. Each rule is tied
to its short form so ordinary words are left alone, and a user's own
replacements run afterwards and still win.
"""

from __future__ import annotations

import re

# Written in capitals whatever case the model gave them. Only short forms
# that are not also ordinary words ("eta", "dm", "lol" are left as typed).
_CAPITALS = (
    "ASAP", "BTW", "FYI", "TBH", "IMO", "IMHO", "IDK", "OMG", "BRB", "EOD",
    "TBD", "FAQ", "WFH", "AFAIK", "IIRC", "TTYL", "NVM",
)

# Spelled out with gaps or dots ("B T W", "F.Y.I.", "I-D-K"): joined up.
_SPELLED = _CAPITALS + ("ETA", "OOO", "DM", "LOL", "DIY")

# (pattern, replacement) for what a short form said as a word came out as.
_MISHEARD: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(?:isap|isep|isab|ay[\s-]sap|a-sap)\b", re.IGNORECASE), "ASAP"),
    (re.compile(r"\bI decay\b(?=\s+(?:what|why|how|if|who|where|when|about)\b)",
                re.IGNORECASE), "IDK"),
    (re.compile(r"\beat etc\b", re.IGNORECASE), "etc"),
    (re.compile(r"\bet\s?cetera\b\.?", re.IGNORECASE), "etc."),
    (re.compile(r"\b(am|is|are|was|be|being|I'm)\s+000\b", re.IGNORECASE), r"\1 OOO"),
]


def _spelled_pattern(form: str) -> re.Pattern[str]:
    letters = r"[\s.\-]+".join(re.escape(ch) for ch in form)
    # At least one gap between letters, so the joined form is not touched here.
    return re.compile(rf"(?<![\w.]){letters}\.?(?![\w])", re.IGNORECASE)


_SPELLED_RES = [(_spelled_pattern(form), form) for form in _SPELLED]
_CAPITALS_RE = re.compile(r"\b(" + "|".join(_CAPITALS) + r")\b", re.IGNORECASE)


def _joined(match: re.Match[str], form: str) -> str:
    """The short form, keeping a full stop only where it ended the sentence
    ("send it by E.O.D." but not "F.Y.I., the office")."""
    if not match.group(0).endswith("."):
        return form
    rest = match.string[match.end():]
    ends_sentence = not rest.strip() or re.match(r"\s+[A-Z]", rest) is not None
    return form + "." if ends_sentence else form


def apply_short_forms(text: str) -> str:
    """ASAP, BTW, FYI... written as short forms, fixed where a model misheard them."""
    if not text:
        return text
    for pattern, replacement in _MISHEARD:
        text = pattern.sub(replacement, text)
    for pattern, form in _SPELLED_RES:
        text = pattern.sub(lambda m, f=form: _joined(m, f), text)
    text = _CAPITALS_RE.sub(lambda m: m.group(1).upper(), text)
    # "etc" with no full stop of its own (a stop that ends the sentence counts).
    text = re.sub(r"\betc\b(?!\.)", "etc.", text)
    return text
