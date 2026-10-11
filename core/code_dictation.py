"""Code dictation -- a Pro feature (see core/license.py): speak identifiers
and symbols, get code typed. "camel case user name" becomes `userName`,
"open paren x close paren" becomes `(x)`.

Pure text in, text out, no model and no network. It runs on the raw
transcript, in place of the normal prose cleanup and punctuation commands:
those would capitalize the first letter and add full stops, which is wrong
for code.

A case command ("camel case", "snake case", ...) takes the words that follow
it, up to the next symbol or case command, and joins them as one identifier.
Words that follow no case command are kept as typed.
"""

from __future__ import annotations

import re

# Spoken case styles -> a function turning a list of lowercase words into one identifier.
_CASE_STYLES = {
    "camel case": lambda w: w[0] + "".join(x.capitalize() for x in w[1:]),
    "pascal case": lambda w: "".join(x.capitalize() for x in w),
    "snake case": lambda w: "_".join(w),
    "upper snake case": lambda w: "_".join(w).upper(),
    "constant case": lambda w: "_".join(w).upper(),
    "kebab case": lambda w: "-".join(w),
    "dot case": lambda w: ".".join(w),
}

# Spoken symbol -> (text, space before, space after). A space before of None
# means "attach to a word before it, like a call, but keep a space after an operator".
_SYMBOLS = {
    "open paren": ("(", None, False),
    "open parenthesis": ("(", None, False),
    "close paren": (")", False, True),
    "close parenthesis": (")", False, True),
    "open bracket": ("[", None, False),
    "close bracket": ("]", False, True),
    "open brace": ("{", True, False),
    "close brace": ("}", False, True),
    "open curly": ("{", True, False),
    "close curly": ("}", False, True),
    "double equals": ("==", True, True),
    "not equals": ("!=", True, True),
    "equals": ("=", True, True),
    "plus": ("+", True, True),
    "minus": ("-", True, True),
    "times": ("*", True, True),
    "divided by": ("/", True, True),
    "less than": ("<", True, True),
    "greater than": (">", True, True),
    "arrow": ("->", True, True),
    "fat arrow": ("=>", True, True),
    "colon": (":", False, True),
    "semicolon": (";", False, True),
    "comma": (",", False, True),
    "dot": (".", False, False),
    "underscore": ("_", False, False),
    "dash": ("-", False, False),
    "slash": ("/", False, False),
    "backslash": ("\\", False, False),
    "hash": ("#", True, False),
    "at sign": ("@", True, False),
    "ampersand": ("&", True, True),
    "pipe": ("|", True, True),
    "quote": ('"', True, True),
    "single quote": ("'", True, True),
    "backtick": ("`", True, True),
}

_LINE_BREAKS = {"new line": "\n", "newline": "\n", "tab": "\t"}

_PHRASES = sorted(
    [*_CASE_STYLES, *_SYMBOLS, *_LINE_BREAKS], key=lambda p: len(p.split()), reverse=True
)
_WORD_RE = re.compile(r"[A-Za-z0-9']+")


def _tokens(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower().replace("-", " "))


def _match_phrase(words: list[str], start: int) -> str | None:
    """The longest command phrase beginning at words[start], if any."""
    for phrase in _PHRASES:
        parts = phrase.split()
        if words[start : start + len(parts)] == parts:
            return phrase
    return None


def to_code(text: str) -> str:
    """Turns a spoken transcript into code text. Empty input gives empty output."""
    words = _tokens(text)
    out: list[str] = []
    glue_next = True  # no space needed before the next piece

    after_word = False  # the last thing emitted was an identifier or plain word

    def emit(
        piece: str,
        space_before: bool | None = True,
        space_after: bool = True,
        *,
        is_word: bool = False,
    ) -> None:
        nonlocal glue_next, after_word
        needs_space = after_word is False if space_before is None else space_before
        if out and needs_space and not glue_next:
            out.append(" ")
        out.append(piece)
        glue_next = not space_after
        after_word = is_word

    i = 0
    while i < len(words):
        phrase = _match_phrase(words, i)
        if phrase is None:
            emit(words[i], is_word=True)
            i += 1
            continue
        i += len(phrase.split())
        if phrase in _CASE_STYLES:
            run: list[str] = []
            while i < len(words) and _match_phrase(words, i) is None:
                run.append(words[i])
                i += 1
            if run:
                emit(_CASE_STYLES[phrase](run), is_word=True)
        elif phrase in _LINE_BREAKS:
            out.append(_LINE_BREAKS[phrase])
            glue_next = True
            after_word = False
        else:
            symbol, before, after = _SYMBOLS[phrase]
            emit(symbol, before, after)
    return "".join(out).strip(" ")
