"""Rule-based transcript cleanup.

Whisper output from casual dictation tends to include filler words ("um",
"uh", "like"), immediately-repeated words ("the the"), and inconsistent
spacing/capitalization. This module fixes those up with plain regexes --
deliberately NOT an LLM/API call (no per-request cost, works fully offline,
runs in microseconds). It's intentionally simple: a handful of well-known
patterns, not a real NLP pipeline, so don't expect it to catch every case.
"""

from __future__ import annotations

import re

# Filler words that are safe to strip as whole words wherever they occur --
# they never form part of a legitimate sentence on their own.
_SIMPLE_FILLERS = ["um", "uh", "uhh", "umm"]
_SIMPLE_FILLER_RE = re.compile(
    r"\b(?:" + "|".join(_SIMPLE_FILLERS) + r")\b[,]?", re.IGNORECASE
)

# "you know" as a filler phrase (e.g. "it was, you know, a lot").
_YOU_KNOW_RE = re.compile(r"\byou know\b[,]?", re.IGNORECASE)

# "like" is unsafe to strip everywhere -- "I like pizza" needs its "like".
# We only strip it when it's clearly being used as a filler/hedge, which in
# practice shows up as "like" set off by commas/pauses on both sides, or
# right at the start of a clause followed by a comma:
#   "it was, like, really loud"   -> ", like," is filler
#   "so like, I went there"       -> leading "like," is filler
# This is a heuristic, not true filler detection -- it will miss fillers
# without surrounding commas and (rarely) could strip a comma-bounded real
# "like", but that pattern is uncommon enough to accept the imperfection
# rather than build real NLP disfluency detection for it.
_LIKE_MIDSENTENCE_RE = re.compile(r",\s*like\s*,", re.IGNORECASE)
# A clause can open with a short filler word before "like," itself
# (e.g. "so like, I went there") -- match past that leading word too, but
# keep it in the output, since it's the "like," that's the filler, not "so".
_LIKE_LEAD_WORDS = ("so", "and", "but", "well", "ok", "okay")
_LIKE_LEADING_RE = re.compile(
    r"(^|[.!?]\s+)((?:" + "|".join(_LIKE_LEAD_WORDS) + r")\s+)?like\s*,\s*",
    re.IGNORECASE,
)

# Collapse an immediately-repeated word ("the the", "I I") into one,
# regardless of case, keeping the first occurrence's casing.
_REPEATED_WORD_RE = re.compile(r"\b(\w+)\b(\s+\1\b)+", re.IGNORECASE)

# Extra space(s) before punctuation, e.g. "hello , world" -> "hello, world".
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([,.!?;:])")

# Multiple whitespace collapsed to a single space.
_MULTI_SPACE_RE = re.compile(r"\s+")


def clean_transcript(text: str) -> str:
    """Strip common filler words/phrases and fix up spacing/capitalization.

    Returns an empty string unchanged (nothing to clean).
    """
    if not text or not text.strip():
        return text

    result = text

    # Filler phrases first, before the repeated-word/spacing passes clean
    # up whatever gaps they leave behind.
    result = _LIKE_MIDSENTENCE_RE.sub(",", result)
    result = _LIKE_LEADING_RE.sub(r"\1\2", result)
    result = _YOU_KNOW_RE.sub("", result)
    result = _SIMPLE_FILLER_RE.sub("", result)

    # Collapse immediately-repeated words produced by dictation stutter.
    result = _REPEATED_WORD_RE.sub(r"\1", result)

    # Spacing cleanup.
    result = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", result)
    result = _MULTI_SPACE_RE.sub(" ", result).strip()

    # Stray leading punctuation left over from a stripped filler at the
    # very start of the text (e.g. "um, so..." -> ", so..." -> "so...").
    result = re.sub(r"^[,;:]\s*", "", result)

    # Capitalize the first letter of the result.
    if result:
        result = result[0].upper() + result[1:]

    return result


if __name__ == "__main__":
    _cases = [
        "um so I was, like, thinking about it",
        "uh the the meeting is at 3 pm",
        "So like, I went to the store",
        "I like pizza a lot",
        "you know it was really loud in there",
        "hello , world .   this  is   a test",
        "umm",
        "",
        "I I I need to go",
    ]
    for _c in _cases:
        print(repr(_c), "->", repr(clean_transcript(_c)))
