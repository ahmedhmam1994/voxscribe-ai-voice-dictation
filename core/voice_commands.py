"""Spoken punctuation/formatting commands ("period", "new line", ...), plus
a single spoken editing command ("scratch that").

Whisper transcribes these as literal words -- this module turns them into
the punctuation/whitespace they name. `is_undo_command()` is deliberately
separate from the punctuation table above: undoing needs to track what
VoxScribe itself typed into the focused window and re-send Backspace, which
is app/main_window.py's job, not this pure-text module's. To keep the
misfire risk low (focus moving, or undoing text the user meant to keep),
it only fires when the ENTIRE dictated utterance is one of the recognized
phrases -- never mid-sentence -- and the caller is expected to additionally
verify the focused window hasn't changed since the last thing was typed.

Opt-in (see core/settings.py's voice_commands_enabled) because a user who
says the literal word "period" or "comma" mid-sentence -- rare, but real --
would otherwise get a surprise symbol instead of the word. Same reasoning
covers "scratch that" -- rare as a literal phrase someone means to dictate,
but real.
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


# Whole-utterance spoken editing phrases -> how much of the last typed text
# to remove. Intentionally short and strict -- matched only against the full
# trimmed dictation (see get_editing_command), never searched for inside a
# longer sentence, and the multi-word phrases are listed first so a phrase
# doesn't get mistaken for a shorter one it starts with.
_EDITING_PHRASES: dict[str, str] = {
    "delete last word": "word",
    "delete that word": "word",
    "scratch that word": "word",
    "delete last sentence": "sentence",
    "delete that sentence": "sentence",
    "scratch that sentence": "sentence",
    "scratch that": "all",
    "undo that": "all",
    "delete that": "all",
    "undo": "all",
}
_TRAILING_PUNCT_RE = re.compile(r"[.!?]+$")


def get_editing_command(text: str) -> str | None:
    """Returns "all", "word", "sentence", or None if the entire dictated
    utterance is (respectively) a spoken undo-everything, delete-last-word,
    delete-last-sentence phrase, or not an editing command at all. Whisper
    often appends a trailing period to short utterances like this, so that's
    stripped before comparing. Returns None for anything longer or
    different -- "scratch that itch" or "delete last word of the email" are
    real dictation, not a command."""
    if not text:
        return None
    normalized = _TRAILING_PUNCT_RE.sub("", text.strip()).strip().lower()
    return _EDITING_PHRASES.get(normalized)


def is_undo_command(text: str) -> bool:
    """True if the entire dictated utterance is a spoken undo-everything
    phrase (not delete-last-word/-sentence). Kept as a thin wrapper around
    get_editing_command for callers that only care about the full-undo case."""
    return get_editing_command(text) == "all"


_SENTENCE_END_CHARS = ".!?"


def compute_deletion(text: str, mode: str) -> tuple[str, int]:
    """Given the text VoxScribe last typed, returns (remaining_text,
    backspace_count) for the requested editing mode ("all", "word", or
    "sentence"). The caller (app/main_window.py) sends `backspace_count`
    Backspace presses and remembers `remaining_text` as the new "last typed"
    state, so a second "delete last word" in a row keeps peeling words off
    rather than re-deleting the same thing.

    "word" strips trailing whitespace, then removes back to the previous
    whitespace boundary (or everything, if it's a single word).

    "sentence" removes back to the previous sentence-ending punctuation
    (. ! ?), ignoring one at the very end of the text itself -- that just
    marks the end of the one sentence being removed, not a boundary to stop
    at. If there's no earlier sentence, it removes everything.
    """
    if mode == "all" or not text:
        return "", len(text)

    if mode == "word":
        stripped = text.rstrip()
        idx = stripped.rfind(" ")
        if idx == -1:
            return "", len(text)
        return stripped[:idx], len(text) - idx

    if mode == "sentence":
        search_area = text[:-1]  # ignore a terminator at the very end
        idx = max(search_area.rfind(ch) for ch in _SENTENCE_END_CHARS)
        if idx == -1:
            return "", len(text)
        return text[: idx + 1], len(text) - (idx + 1)

    raise ValueError(f"unknown editing mode: {mode!r}")


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
