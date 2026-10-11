"""Smart formatting -- a Pro feature (see core/license.py): spoken emails,
web addresses and numbers typed the way they are written.

    "john dot smith at gmail dot com"  ->  john.smith@gmail.com
    "example dot com slash pricing"    ->  example.com/pricing
    "twenty five percent"              ->  25%
    "one hundred and five dollars"     ->  $105
    "five five five one two three four" -> 5551234

Rules only, no model and no network. Whisper often writes numbers well on its
own, so this stays conservative: a lone small number ("one of them") is left as
a word, and a number phrase that does not parse cleanly ("twenty twenty six")
is left untouched.
"""

from __future__ import annotations

import re

_ONES = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19,
}  # fmt: skip
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}  # fmt: skip
_SCALES = {"hundred": 100, "thousand": 1_000, "million": 1_000_000}
_DIGITS = {name: value for name, value in _ONES.items() if value < 10}

_NUMBER_WORD = "|".join([*_ONES, *_TENS, *_SCALES])
_DIGIT_WORD = "|".join(_DIGITS)
_RUN = rf"(?:{_NUMBER_WORD})(?:[\s-]+(?:and[\s-]+)?(?:{_NUMBER_WORD}))*"
_NUMBER_RE = re.compile(
    rf"\b(?P<whole>{_RUN})(?:\s+point\s+(?P<decimals>(?:{_DIGIT_WORD})(?:\s+(?:{_DIGIT_WORD}))*))?"
    r"(?:\s+(?P<unit>percent|dollars?|euros?))?\b",
    re.IGNORECASE,
)
_PHONE_RE = re.compile(
    rf"\b(?:(?:{_DIGIT_WORD}|oh)(?:[\s,-]+|\b)){{7,}}", re.IGNORECASE
)

_TLDS = "com|org|net|io|co|edu|gov|app|dev|ai|me|info|uk|de|fr"
_PART = r"[a-z0-9]+"
_LOCAL = rf"{_PART}(?:\s+(?:dot|underscore|dash)\s+{_PART})*"
_DOMAIN = rf"{_PART}(?:\s+(?:dot|dash)\s+{_PART})*\s+dot\s+(?:{_TLDS})"
_EMAIL_RE = re.compile(rf"\b(?P<local>{_LOCAL})\s+at\s+(?P<domain>{_DOMAIN})\b", re.IGNORECASE)
_URL_RE = re.compile(
    rf"\b(?P<scheme>https?\s+colon\s+slash\s+slash\s+)?(?P<host>(?:w\s+w\s+w\s+dot\s+)?{_DOMAIN})"
    rf"(?P<path>(?:\s+slash\s+{_PART}(?:\s+(?:dash|dot|underscore)\s+{_PART})*)*)\b",
    re.IGNORECASE,
)

# Ordinary words that precede "at" in a sentence ("look at example dot com"),
# so they are not read as the start of an email address.
_NOT_A_LOCAL_PART = {
    "look", "looking", "meet", "meeting", "here", "there", "arrive", "arrived", "good",
    "glad", "stay", "stop", "start", "starting", "aimed", "stare", "smile", "laugh",
    "work", "working", "available", "ready", "come", "go", "sit", "stand", "wait",
    "back", "out", "up", "down", "once", "least", "most", "all", "what", "who",
}  # fmt: skip

_SPOKEN_SYMBOLS = {"dot": ".", "underscore": "_", "dash": "-", "slash": "/"}


def _join_spoken(words: str) -> str:
    """"john dot smith" -> "john.smith"."""
    pieces = words.lower().split()
    return "".join(_SPOKEN_SYMBOLS.get(piece, piece) for piece in pieces)


def _email(match: re.Match[str]) -> str:
    local = match.group("local")
    if local.split()[0].lower() in _NOT_A_LOCAL_PART and len(local.split()) == 1:
        return match.group(0)
    return f"{_join_spoken(local)}@{_join_spoken(match.group('domain'))}"


def _url(match: re.Match[str]) -> str:
    spoken_scheme = (match.group("scheme") or "").lower()
    scheme = "https://" if "https" in spoken_scheme else "http://" if spoken_scheme else ""
    host = _join_spoken(match.group("host")).removeprefix("www.")
    if match.group("host").lower().startswith("w w w"):
        host = "www." + host
    return f"{scheme}{host}{_join_spoken(match.group('path') or '')}"


def _phone(match: re.Match[str]) -> str:
    digits = []
    for word in re.findall(r"[a-z]+", match.group(0).lower()):
        digits.append("0" if word == "oh" else str(_DIGITS[word]))
    return "".join(digits) + (" " if match.group(0).endswith((" ", ",", "-")) else "")


def parse_number_words(phrase: str) -> int | None:
    """"one hundred and five" -> 105. None if the words are not a clean number."""
    total = 0
    current = 0
    previous = ""  # "ones", "teens", "tens" or "scale"
    for word in re.split(r"[\s-]+", phrase.lower()):
        if word == "and":
            continue
        if word in _SCALES:
            scale = _SCALES[word]
            if scale == 100:
                current = max(current, 1) * 100
            else:
                total += max(current, 1) * scale
                current = 0
            previous = "scale"
        elif word in _TENS:
            if previous in {"ones", "teens", "tens"}:
                return None
            current += _TENS[word]
            previous = "tens"
        elif word in _ONES:
            value = _ONES[word]
            if previous in {"ones", "teens"} or (previous == "tens" and value >= 10):
                return None
            current += value
            previous = "ones" if value < 10 else "teens"
        else:
            return None
    return total + current


def _number(match: re.Match[str]) -> str:
    value = parse_number_words(match.group("whole"))
    if value is None:
        return match.group(0)
    decimals = match.group("decimals")
    unit = (match.group("unit") or "").lower()
    if decimals:
        text = f"{value}." + "".join(str(_DIGITS[w]) for w in decimals.lower().split())
    else:
        text = str(value)
    if unit == "percent":
        return f"{text}%"
    if unit.startswith("dollar"):
        return f"${text}"
    if unit.startswith("euro"):
        return f"€{text}"
    if value < 10 and not decimals:
        return match.group(0)  # a lone small number reads better as a word
    return text


def smart_format(text: str) -> str:
    """Rewrites spoken emails, web addresses and numbers. Other text is unchanged."""
    if not text:
        return text
    text = _EMAIL_RE.sub(_email, text)
    text = _URL_RE.sub(_url, text)
    text = _PHONE_RE.sub(_phone, text)
    return _NUMBER_RE.sub(_number, text)
