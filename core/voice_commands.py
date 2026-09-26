"""Spoken punctuation/formatting commands ("period", "new line", ...).

Whisper transcribes these as literal words -- this module turns them into
the punctuation/whitespace they name. Deliberately scoped to punctuation and
line breaks only (no "scratch that"/"undo" editing commands): those would
need to track what VoxScribe itself typed into the focused window and could
misfire if focus moved, which is a bigger, riskier feature than this one.

Opt-in (see core/settings.py's voice_commands_enabled) because a user who
says the literal word "period" or "comma" mid-sentence -- rare, but real --
would otherwise get a surprise symbol instead of the word.
"""

from __future__ import annotations

import re

# (spoken phrase, replacement symbol, category). Longer/more-specific
# phrases are listed before shorter ones that could be a prefix of them
# ("full stop" before "period" doesn't matter since they don't overlap, but
# keeping multi-word phrases above single-word ones avoids any future
# accidental prefix collisions).
#
# category meanings:
#   "end"     sentence-ending punctuation (. ! ?) -- no space before, one
#             space after, and the next letter gets capitalized.
#   "mid"     inline punctuation (, : ;) -- no space before, one space after.
#   "newline" a line/paragraph break -- no space on either side, and the
#             next letter gets capitalized (new line/paragraph starts a
#             fresh sentence in practice).
#   "open"    an opening bracket/quote -- space before, none after (attaches
#             to the next word).
#   "close"   a closing bracket/quote -- no space before (attaches to the
#             previous word), space after.
_COMMANDS: list[tuple[str, str, str]] = [
    ("new paragraph", "\n\n", "newline"),
    ("new line", "\n", "newline"),
    ("question mark", "?", "end"),
    ("exclamation mark", "!", "end"),
    ("exclamation point", "!", "end"),
    ("open quote", '"', "open"),
    ("close quote", '"', "close"),
    ("open parenthesis", "(", "open"),
    ("close parenthesis", ")", "close"),
    ("open paren", "(", "open"),
    ("close paren", ")", "close"),
    ("full stop", ".", "end"),
    ("period", ".", "end"),
    ("comma", ",", "mid"),
    ("colon", ":", "mid"),
    ("semicolon", ";", "mid"),
]

# Marks a spot where the following letter should be capitalized, inserted
# right after an "end"/"newline" symbol. Removed in the final pass. Chosen
# as a control character that will never appear in real transcribed text.
_CAP_MARK = "\x00"

_TRAILING_SPACE_TAB_RE = re.compile(r"[ \t]*\n[ \t]*")
_MULTI_SPACE_TAB_RE = re.compile(r"[ \t]+")
_SPACE_BEFORE_PUNCT_RE = re.compile(r"[ \t]+([,.!?;:])")
_CAP_NEXT_LETTER_RE = re.compile(_CAP_MARK + r"([ \t\n]*)([a-z])")


def _phrase_re(phrase: str) -> re.Pattern[str]:
    # \s+ between words lets "new  line" (double space from Whisper) still
    # match; the surrounding \s* eats whitespace VoxScribe should replace
    # rather than leave dangling once the phrase itself is gone.
    core = r"\s+".join(re.escape(word) for word in phrase.split(" "))
    return re.compile(r"\s*\b" + core + r"\b\s*", re.IGNORECASE)


_COMPILED_COMMANDS = [
    (_phrase_re(phrase), symbol, category) for phrase, symbol, category in _COMMANDS
]


def apply_voice_commands(text: str) -> str:
    """Replace spoken punctuation/formatting commands with real symbols.

    Returns the text unchanged if it's empty. Safe to call on text that
    contains no commands at all -- it just won't match anything.
    """
    if not text or not text.strip():
        return text

    result = text
    for pattern, symbol, category in _COMPILED_COMMANDS:
        if category == "end":
            replacement = symbol + " " + _CAP_MARK
        elif category == "newline":
            replacement = symbol + _CAP_MARK
        elif category == "mid":
            replacement = symbol + " "
        elif category == "open":
            # Keep one space before (separating it from the prior word) but
            # none after, so it attaches to the word that follows.
            replacement = " " + symbol
        else:  # "close" -- attach to the previous word, space after
            replacement = symbol + " "
        result = pattern.sub(replacement, result)

    # Clean up spacing left behind by substitution: no space before mid/end
    # punctuation, no space padding around inserted newlines, collapse any
    # remaining run of spaces/tabs.
    result = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", result)
    result = _TRAILING_SPACE_TAB_RE.sub("\n", result)
    result = _MULTI_SPACE_TAB_RE.sub(" ", result)

    # Capitalize the letter right after each inserted end-of-sentence/
    # newline command, then drop the marker.
    result = _CAP_NEXT_LETTER_RE.sub(lambda m: m.group(1) + m.group(2).upper(), result)
    result = result.replace(_CAP_MARK, "")

    return result.strip()


if __name__ == "__main__":
    _cases = [
        "hello comma world period",
        "dear team new paragraph the meeting is at 3 pm period",
        "she said open quote hello close quote and left",
        "what time is it question mark",
        "call me maybe exclamation point",
        "item one colon apples comma oranges semicolon and pears",
        "no commands here at all",
        "",
    ]
    for _c in _cases:
        print(repr(_c), "->", repr(apply_voice_commands(_c)))
