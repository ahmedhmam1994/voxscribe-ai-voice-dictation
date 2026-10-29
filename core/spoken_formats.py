"""Spoken formats: numbers, doses and references typed the way a professional
writes them. It follows the term packs that are switched on (core/term_packs.py):

Medical
    "one twenty over eighty"                  -> 120/80
    "five milligrams twice daily"             -> 5 mg BID
    "ten milligrams by mouth every eight hours" -> 10 mg PO q8h
    "ninety eight percent"                    -> 98%
Law
    "section twelve subsection b"             -> Section 12(b)
    "clause four point two"                   -> clause 4.2
    "Smith versus Jones"                      -> Smith v. Jones
Business
    "fifty thousand dollars"                  -> $50,000
    "two point five million dollars"          -> $2.5 million
    "twenty percent"                          -> 20%
    "q three"                                 -> Q3

Rules only, no model and no network, and deliberately narrow: a number is only
rewritten next to the unit, keyword or symbol that shows what it is ("five
milligrams", "section twelve"), so a plain "one of them" stays a word. Blood
pressure needs both numbers to be plausible. Off by default (Settings, Text).
"""

from __future__ import annotations

import re

from core.smart_format import _DIGITS, _ONES, _TENS, parse_number_words

_WORDS = "|".join([*_ONES, *_TENS, "hundred", "thousand"])
# "and" only joins after hundred or thousand ("one hundred and five"), never two
# separate numbers ("section nine and fifty dollars").
_RUN = (
    rf"(?:a\s+)?(?:{_WORDS})"
    rf"(?:[\s-]+(?:{_WORDS})|(?:(?<=hundred)|(?<=thousand))\s+and\s+(?:{_WORDS}))*"
)
# Speech models often write the digits themselves ("5 milligrams"), so every rule
# accepts digits as well as number words.
_AMOUNT = rf"(?:\d+(?:,\d{{3}})*(?:\.\d+)?|{_RUN})"
_DIGIT_WORDS = "|".join(["oh", *_DIGITS])
_DIGIT_SEQ = rf"(?:{_DIGIT_WORDS})(?:\s+(?:{_DIGIT_WORDS}))*"
_HUNDREDS_DIGITS = {name: value for name, value in _DIGITS.items() if 1 <= value <= 9}
_FLAGS = re.IGNORECASE


def spoken_int(phrase: str) -> int | None:
    """"one hundred and five" -> 105, "one twenty" -> 120 (the way blood pressure is
    said), "a hundred" -> 100. None if the words are not a clean number."""
    cleaned = phrase.strip().replace(",", "")
    if re.fullmatch(r"\d+", cleaned):
        return int(cleaned)
    words = re.split(r"[\s-]+", phrase.lower().strip())
    if words and words[0] == "a":
        words[0] = "one"
    value = parse_number_words(" ".join(words))
    if value is not None:
        return value
    if len(words) >= 2 and words[0] in _HUNDREDS_DIGITS:
        rest = parse_number_words(" ".join(words[1:]))
        if rest is not None and 10 <= rest <= 99:
            return _HUNDREDS_DIGITS[words[0]] * 100 + rest
    return None


def _decimals(words: str | None) -> str:
    if not words:
        return ""
    digits = ["0" if w == "oh" else str(_DIGITS[w]) for w in words.lower().split()]
    return "." + "".join(digits)


def _number(whole: str | None, decimals: str | None) -> str | None:
    """"five", "two" + "five" -> "5", "2.5"; None when the words are not a number."""
    if whole and re.fullmatch(r"\d+(?:,\d{3})*(?:\.\d+)?", whole.strip()):
        return None if decimals else whole.strip().replace(",", "")
    value = 0
    if whole:
        parsed = spoken_int(whole)
        if parsed is None:
            return None
        value = parsed
    elif not decimals:
        return None
    return f"{value}{_decimals(decimals)}"


# -- medical ---------------------------------------------------------------------

_MISHEARD_PRESSURE = re.compile(
    r"(?<![\w-])(?:on|one|won)\s+(?P<tens>\d{2})\s+over\s+(?P<dia>\d{2,3})\b", _FLAGS
)
_BLOOD_PRESSURE = re.compile(rf"(?<![\w-])(?P<sys>{_AMOUNT})\s+over\s+(?P<dia>{_AMOUNT})\b", _FLAGS)


def _blood_pressure(match: re.Match[str]) -> str:
    systolic = spoken_int(match.group("sys"))
    diastolic = spoken_int(match.group("dia"))
    if (
        systolic is None
        or diastolic is None
        or not 60 <= systolic <= 300
        or not 30 <= diastolic <= 200
        or diastolic >= systolic
    ):
        return match.group(0)
    return f"{systolic}/{diastolic}"


def _misheard_pressure(match: re.Match[str]) -> str:
    """"one twenty over eighty" is often written "on 20 over 80"."""
    systolic, diastolic = 100 + int(match.group("tens")), int(match.group("dia"))
    if 60 <= systolic <= 300 and 30 <= diastolic <= 200 and diastolic < systolic:
        return f"{systolic}/{diastolic}"
    return match.group(0)


_UNITS = {
    "milligram": "mg", "microgram": "mcg", "milliliter": "mL", "millilitre": "mL",
    "gram": "g", "kilogram": "kg", "milliequivalent": "mEq",
}  # fmt: skip
_DOSE = re.compile(
    rf"(?<![\w-])(?:(?P<whole>{_AMOUNT})(?:\s+point\s+(?P<dec>{_DIGIT_SEQ}))?|point\s+(?P<dec2>{_DIGIT_SEQ}))"
    r"\s+(?P<unit>milligrams?|micrograms?|milliliters?|millilitres?|grams?|kilograms?"
    r"|milliequivalents?)\b",
    _FLAGS,
)


def _dose(match: re.Match[str]) -> str:
    number = _number(match.group("whole"), match.group("dec") or match.group("dec2"))
    if number is None:
        return match.group(0)
    unit = match.group("unit").lower().rstrip("s")
    return f"{number} {_UNITS[unit]}"


_AFTER_DOSE = re.compile(
    r"(?P<dose>\b\d[\d.]*\s(?:mg|mcg|mL|g|kg|mEq))"
    rf"(?P<tail>(?:\s+(?:by\s+mouth|twice\s+(?:a\s+day|daily)|three\s+times\s+(?:a\s+day|daily)"
    rf"|four\s+times\s+(?:a\s+day|daily)|every\s+(?:{_AMOUNT})\s+hours?|as\s+needed))+)",
    _FLAGS,
)
_TAIL_PARTS = [
    (re.compile(r"\bby\s+mouth\b", _FLAGS), "PO"),
    (re.compile(r"\btwice\s+(?:a\s+day|daily)\b", _FLAGS), "BID"),
    (re.compile(r"\bthree\s+times\s+(?:a\s+day|daily)\b", _FLAGS), "TID"),
    (re.compile(r"\bfour\s+times\s+(?:a\s+day|daily)\b", _FLAGS), "QID"),
    (re.compile(r"\bas\s+needed\b", _FLAGS), "PRN"),
]
_EVERY_HOURS = re.compile(rf"\bevery\s+(?P<n>{_AMOUNT})\s+hours?\b", _FLAGS)


def _every_hours(match: re.Match[str]) -> str:
    hours = spoken_int(match.group("n"))
    return f"q{hours}h" if hours is not None and 1 <= hours <= 48 else match.group(0)


def _after_dose(match: re.Match[str]) -> str:
    tail = match.group("tail")
    for pattern, short in _TAIL_PARTS:
        tail = pattern.sub(short, tail)
    tail = _EVERY_HOURS.sub(_every_hours, tail)
    return match.group("dose") + tail


# -- percent (medical and business) ---------------------------------------------

_PERCENT = re.compile(
    rf"(?<![\w-])(?P<whole>{_AMOUNT})(?:\s+point\s+(?P<dec>{_DIGIT_SEQ}))?\s+percent\b", _FLAGS
)


def _percent(match: re.Match[str]) -> str:
    number = _number(match.group("whole"), match.group("dec"))
    return match.group(0) if number is None else f"{number}%"


# -- law ---------------------------------------------------------------------------

_SUB_KEYWORD = r"(?:subsection|sub\s+section|subparagraph|sub\s+paragraph|paragraph|subclause)"
_REFERENCE = re.compile(
    r"\b(?P<kw>section|clause|article|paragraph|chapter|rule|schedule|exhibit|appendix)"
    rf"\s+(?P<num>{_AMOUNT})(?:\s+point\s+(?P<dec>{_DIGIT_SEQ}))?"
    rf"(?P<subs>(?:\s+{_SUB_KEYWORD}\s+(?:[a-z]\b|{_AMOUNT}))*)",
    _FLAGS,
)
_SUB_PART = re.compile(rf"{_SUB_KEYWORD}\s+(?P<part>[a-z]\b|{_AMOUNT})", _FLAGS)


def _reference(match: re.Match[str]) -> str:
    number = _number(match.group("num"), match.group("dec"))
    if number is None:
        return match.group(0)
    subs = ""
    for part in _SUB_PART.finditer(match.group("subs") or ""):
        text = part.group("part")
        value = text.lower() if len(text) == 1 else spoken_int(text)
        if value is None:
            return match.group(0)
        subs += f"({value})"
    return f"{match.group('kw')} {number}{subs}"


_VERSUS = re.compile(r"\b([A-Z][\w'’-]+)\s+(?:versus|vs\.?)\s+(?=[A-Z])")

# -- business ------------------------------------------------------------------------

_MONEY = re.compile(
    rf"(?<![\w-])(?P<whole>{_AMOUNT})(?:\s+point\s+(?P<dec>{_DIGIT_SEQ}))?"
    r"(?:\s+(?P<big>million|billion|trillion))?\s+(?P<cur>dollars|euros)\b",
    _FLAGS,
)
_SYMBOLS = {"dollars": "$", "euros": "€"}


def _money(match: re.Match[str]) -> str:
    number = _number(match.group("whole"), match.group("dec"))
    if number is None:
        return match.group(0)
    symbol = _SYMBOLS[match.group("cur").lower()]
    big = (match.group("big") or "").lower()
    if big:
        return f"{symbol}{number} {big}"
    whole, dot, fraction = number.partition(".")
    return f"{symbol}{int(whole):,}{dot}{fraction}"


_QUARTER = re.compile(r"\bq\s*(one|two|three|four)\b", _FLAGS)
_QUARTER_NUMBER = {"one": 1, "two": 2, "three": 3, "four": 4}


def apply_spoken_formats(text: str, packs: list[str]) -> str:
    """Rewrites the spoken numbers that the enabled `packs` call for."""
    if not text or not packs:
        return text
    if "medical" in packs:
        text = _MISHEARD_PRESSURE.sub(_misheard_pressure, text)
        text = _BLOOD_PRESSURE.sub(_blood_pressure, text)
        text = _DOSE.sub(_dose, text)
        text = _AFTER_DOSE.sub(_after_dose, text)
    if "medical" in packs or "business" in packs:
        text = _PERCENT.sub(_percent, text)
    if "legal" in packs:
        text = _REFERENCE.sub(_reference, text)
        text = _VERSUS.sub(lambda m: f"{m.group(1)} v. ", text)
    if "business" in packs:
        text = _MONEY.sub(_money, text)
        text = _QUARTER.sub(lambda m: f"Q{_QUARTER_NUMBER[m.group(1).lower()]}", text)
    return text
