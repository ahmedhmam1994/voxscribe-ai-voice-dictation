"""Speak once, fill the whole form: "Name Sam Lee, phone 0100 123 4567, email
sam at gmail dot com" puts each part into the box with that label.

The boxes and their labels come from the window (core/form_fields.py reads
them through UI Automation); this module only matches the spoken labels to
them, on this PC, with no language model. It is the same logic as the
Android app's FormFill.kt, so both apps understand the same sentences.

To keep ordinary dictation ordinary, a sentence fills a form only when it
starts with a box's label and names at least two of the boxes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# What a box holds, so its value is typed the way the box expects.
TEXT, EMAIL, URL, NUMBER, PHONE = "text", "email", "url", "number", "phone"
# A dropdown (its option is picked by typing its name) and a date box.
CHOICE, DATE = "choice", "date"


@dataclass(frozen=True)
class Field:
    """A box in the window: its position in screen order, its label, its kind."""

    index: int
    label: str
    kind: str = TEXT
    # For a date box, how it wants the date: "MDY" for a date picker's parts
    # in order (month, day, year), or a typed pattern such as "DD/MM/YYYY".
    # Empty: the date is typed as it was said.
    pattern: str = ""


@dataclass(frozen=True)
class Fill:
    """What to type into the box at `index`."""

    index: int
    value: str


MIN_FIELDS = 2

# Ways people say a common label. A box labelled with any of these answers to
# all of them, so "Mobile number" answers to "phone".
_GROUPS: list[list[str]] = [
    ["first name", "given name", "forename"],
    ["last name", "surname", "family name"],
    ["middle name"],
    ["full name", "name", "your name"],
    [
        "phone number", "phone", "mobile number", "mobile", "telephone",
        "cell phone", "cell", "contact number",
    ],
    ["email address", "email", "e mail", "e mail address", "mail"],
    ["street address", "address", "street", "address line 1"],
    ["address line 2", "apartment", "flat", "suite"],
    ["city", "town"],
    ["zip code", "zip", "postcode", "post code", "postal code"],
    ["state", "province", "region", "county"],
    ["country"],
    ["company", "company name", "organization", "organisation", "business"],
    ["job title", "position", "role"],
    ["date of birth", "birthday", "birth date", "dob"],
    ["age"],
    ["website", "web site", "url"],
    ["subject", "title"],
    ["message", "notes", "note", "comments", "comment", "description"],
]

_KIND_OF_GROUP = {"phone": PHONE, "email": EMAIL, "website": URL}

# Spoken before the first label without making the sentence ordinary speech.
_LEAD_INS = {"fill", "form", "my"}

# "User name" and "Pet name" are not the person's name.
_NOT_A_KIND = {
    "user", "nick", "screen", "display", "account", "pet", "file", "domain",
    "host", "project", "team", "group",
}

_WHOLE_NAME = {"name", "full name", "your name"}

_WORD = re.compile(r"[^\W_]+")
_LABEL_NOISE = re.compile(
    r"\(.*?\)|[*:]|\boptional\b|\brequired\b|\benter\b|\btype\b|\byour\b"
)
_ID_PREFIXES = {"et", "edit", "edittext", "input", "txt", "text", "field", "tv", "til", "tb"}


def normalize_label(label: str) -> str:
    """"Phone number *" or "Enter your e-mail:" as "phone number" / "e mail"."""
    return " ".join(_WORD.findall(_LABEL_NOISE.sub(" ", label.lower())))


def label_from_id(automation_id: str | None) -> str | None:
    """"et_phone_number" or "inputEmail" as "phone number" / "email", for a
    box with no visible label."""
    if not automation_id:
        return None
    name = automation_id.split("/", 1)[-1]
    if not name.strip():
        return None
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", name).lower()
    words = [w for w in re.split(r"[^a-z0-9]+", spaced) if w and w not in _ID_PREFIXES]
    return " ".join(words) or None


def _group_of(bare: str) -> list[str] | None:
    padded = f" {bare} "
    best: tuple[list[str], int] | None = None
    for group in _GROUPS:
        lengths = [len(p) for p in group if f" {p} " in padded]
        if lengths and (best is None or max(lengths) > best[1]):
            best = (group, max(lengths))
    return best[0] if best else None


def aliases(label: str) -> set[str]:
    """Every way the box labelled `label` may be said. Empty when the label
    has no words."""
    bare = normalize_label(label)
    if not bare:
        return set()
    # The group whose longest phrase fits the label best: "first name" before "name".
    group = _group_of(bare)
    # A label that is a group phrase itself takes the whole group; "Name of pet" stays itself.
    if group is not None and bare in group:
        return set(group) | {bare}
    # "Customer name" or "Home phone" ends in a common label, so it answers to it too.
    words = bare.split(" ")
    if len(words) > 1 and words[0] not in _NOT_A_KIND:
        for candidate in _GROUPS:
            if any(bare.endswith(f" {p}") for p in candidate):
                return set(candidate) | {bare}
    return {bare}


def kind_of_label(label: str) -> str:
    """Email, phone or web address boxes by their label, the rest text."""
    names = aliases(label)
    for first, kind in _KIND_OF_GROUP.items():
        if first in names:
            return kind
    return TEXT


@dataclass
class _Word:
    text: str
    start: int
    end: int


@dataclass
class _Hit:
    field: Field
    first: int
    last: int
    alias: str


def plan(spoken: str, fields: list[Field]) -> list[Fill] | None:
    """What to type where, or None when `spoken` is not a form sentence for
    `fields`. Fields without a label are ignored."""
    alias_sets = {f.index: aliases(f.label) for f in fields}
    labelled = [f for f in fields if alias_sets[f.index]]
    if len(labelled) < MIN_FIELDS:
        return None
    words = [_Word(m.group().lower(), m.start(), m.end()) for m in _WORD.finditer(spoken)]
    if not words:
        return None

    # A form with First name and Last name boxes but no Name box: "name Sam Lee" fills both.
    has_whole = any(alias_sets[f.index] & _WHOLE_NAME for f in labelled)
    first_box = next((f for f in labelled if "first name" in alias_sets[f.index]), None)
    if has_whole:
        first_box = None
    last_box = next((f for f in labelled if "last name" in alias_sets[f.index]), None)
    alias_words: dict[int, list[list[str]]] = {}
    for f in labelled:
        names = set(alias_sets[f.index])
        if f == first_box and last_box is not None:
            names |= _WHOLE_NAME
        alias_words[f.index] = [a.split(" ") for a in names]

    used: set[int] = set()
    hits: list[_Hit] = []
    i = 0
    while i < len(words):
        # The longest label said here, given to the first box with it that is still empty.
        best: _Hit | None = None
        for f in labelled:
            if f.index in used:
                continue
            for alias in alias_words[f.index]:
                last = i + len(alias) - 1
                if last >= len(words):
                    continue
                if all(words[i + k].text == alias[k] for k in range(len(alias))) and (
                    best is None or last > best.last
                ):
                    best = _Hit(f, i, last, " ".join(alias))
        if best is not None:
            hits.append(best)
            used.add(best.field.index)
            i = best.last + 1
        else:
            i += 1
    if len(hits) < MIN_FIELDS:
        return None
    opening = hits[0].first
    if opening > 1 or (opening == 1 and words[0].text not in _LEAD_INS):
        return None

    stops = _label_stops(spoken, words)
    fills: list[Fill] = []
    for n, hit in enumerate(hits):
        start = words[hit.last].end
        end = words[hits[n + 1].first].start if n + 1 < len(hits) else len(spoken)
        # ", country Egypt" with no Country box still ends the value before it.
        end = min([end] + [s for s in stops if start < s < end])
        value = clean_value(spoken[start:end], hit.field.kind, hit.field.pattern)
        if (
            first_box is not None
            and hit.field == first_box
            and hit.alias in _WHOLE_NAME
            and last_box is not None
            and last_box.index not in used
        ):
            fills.extend(_split_name(value, hit.field.index, last_box.index))
        else:
            fills.append(Fill(hit.field.index, value))
    fills = [f for f in fills if f.value]
    return fills if len(fills) >= MIN_FIELDS else None


_COMMON_LABELS = sorted(
    {tuple(p.split(" ")) for group in _GROUPS for p in group}, key=len, reverse=True
)


def _label_stops(spoken: str, words: list[_Word]) -> list[int]:
    """Where a common label starts right after a comma or full stop: the end
    of the value before it, even when the window has no box for that label."""
    stops = []
    for i, word in enumerate(words):
        before = spoken[words[i - 1].end : word.start] if i else ""
        if not any(mark in before for mark in ",.;"):
            continue
        for label in _COMMON_LABELS:
            if tuple(w.text for w in words[i : i + len(label)]) == label:
                stops.append(word.start)
                break
    return stops


def starts_like_a_form(spoken: str) -> bool:
    """True when `spoken` opens with a common label and names at least two, so
    it is worth reading the boxes in the window. Cheap: no UI Automation."""
    fields = [Field(i, group[0]) for i, group in enumerate(_GROUPS)]
    return plan(spoken, fields) is not None


def _split_name(value: str, first_index: int, last_index: int) -> list[Fill]:
    """"Sam Lee" as Sam in the first name box and Lee in the last name box."""
    parts = value.split()
    if len(parts) < 2:
        return [Fill(first_index, value)]
    return [Fill(first_index, " ".join(parts[:-1])), Fill(last_index, parts[-1])]


_CONNECTOR = re.compile(r"^(?:is|are|=)\s+", re.IGNORECASE)
_TRAILING_AND = re.compile(r"\s+and$", re.IGNORECASE)


def clean_value(raw: str, kind: str = TEXT, pattern: str = "") -> str:
    """" is Sam Lee, " as "Sam Lee"; email, web, number and phone boxes get
    the form they expect."""
    value = raw.strip().strip(",;:.-").strip()
    value = _CONNECTOR.sub("", value)
    value = _TRAILING_AND.sub("", value).strip().rstrip(",;.").strip()
    if kind == DATE:
        return format_date(value, pattern).strip()
    return shape(value, kind).strip()


# -- typing a value the way the box expects (FieldShape.kt) --------------------

_DIGIT_WORDS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
}
_EMAIL_WORDS = {"at": "@", "dot": ".", "underscore": "_", "dash": "-", "hyphen": "-"}
_URL_WORDS = {**_EMAIL_WORDS, "slash": "/", "colon": ":"}


def shape(text: str, kind: str) -> str:
    if kind == EMAIL:
        return _address(text, _EMAIL_WORDS)
    if kind == URL:
        return _address(text, _URL_WORDS)
    if kind == PHONE:
        return _phone(text)
    if kind == NUMBER:
        return "".join(c for c in _spell_digits(text) if c.isdigit())
    return text


def _address(text: str, spoken: dict[str, str]) -> str:
    out = []
    for word in text.split():
        bare = word.strip(",;!?").lower()
        out.append(spoken.get(bare) or _DIGIT_WORDS.get(bare) or bare)
    # A spoken sentence ends with a full stop; an address does not.
    return "".join(out).rstrip(".,!?")


def _spell_digits(text: str) -> str:
    return "".join(_DIGIT_WORDS.get(w.strip(",.!?").lower(), w) for w in text.split())


def _phone(text: str) -> str:
    out = []
    for word in text.split():
        bare = word.strip(",.!?").lower()
        if bare in _DIGIT_WORDS:
            out.append(_DIGIT_WORDS[bare])
        elif bare == "oh":
            out.append("0")
        elif bare == "plus":
            out.append("+")
        elif bare == "star":
            out.append("*")
        elif bare in ("hash", "pound"):
            out.append("#")
        else:
            out.append(bare)
    return "".join(c for c in "".join(out) if c.isdigit() or c in "+*#")


# -- dates -----------------------------------------------------------------------

_MONTHS = {
    name: i + 1
    for i, names in enumerate(
        [
            ("january", "jan"), ("february", "feb"), ("march", "mar"), ("april", "apr"),
            ("may",), ("june", "jun"), ("july", "jul"), ("august", "aug"),
            ("september", "sep", "sept"), ("october", "oct"), ("november", "nov"),
            ("december", "dec"),
        ]
    )
    for name in names
}
_ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
    "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12,
    "thirteenth": 13, "fourteenth": 14, "fifteenth": 15, "sixteenth": 16,
    "seventeenth": 17, "eighteenth": 18, "nineteenth": 19, "twentieth": 20,
    "thirtieth": 30,
}
_DATE_PATTERN = re.compile(
    r"(?i)\b(dd|mm|yyyy|yy)[./\- ]+(dd|mm|yyyy|yy)[./\- ]+(dd|mm|yyyy|yy)\b"
)


def parse_date(text: str) -> tuple[int, int, int] | None:
    """(year, month, day) from a spoken date with its month named: "5 March
    1990", "March 5th, 1990", "the fifth of March 1990", "2nd Jan 2001".
    None for anything else, such as "5/3/1990", whose order is unclear."""
    words = re.findall(r"[a-z]+|\d+", text.lower())
    month = day = year = None
    pending_tens = 0
    for word in words:
        if word in _MONTHS and month is None:
            month = _MONTHS[word]
        elif word.isdigit():
            n = int(word)
            if len(word) == 4 and year is None:
                year = n
            elif 1 <= n <= 31 and day is None:
                day = n
        elif word in ("twenty", "thirty") and day is None:
            pending_tens = 20 if word == "twenty" else 30
        elif word in _ORDINALS and day is None:
            day = pending_tens + _ORDINALS[word] if pending_tens else _ORDINALS[word]
            pending_tens = 0
        elif word.endswith(("st", "nd", "rd", "th")) and word[:-2].isdigit() and day is None:
            day = int(word[:-2])
    if pending_tens and day is None:
        day = pending_tens
    if month is None or day is None or year is None or not 1 <= day <= 31:
        return None
    return year, month, day


def date_pattern(hint: str) -> str:
    """"DD/MM/YYYY" when a box's hint shows the format it wants, else ""."""
    match = _DATE_PATTERN.search(hint)
    return match.group(0).upper() if match else ""


def format_date(text: str, pattern: str) -> str:
    """The spoken date in the form the box wants. A date picker ("MDY")
    takes the digits of each part in its order; a typed pattern gets its
    parts filled in. A date that cannot be read is typed as said, except into
    a date picker, which gets nothing."""
    parsed = parse_date(text)
    if not pattern:
        return text
    if parsed is None:
        return "" if pattern.isalpha() and len(pattern) == 3 else text
    year, month, day = parsed
    if pattern.isalpha() and len(pattern) == 3:
        parts = {"M": f"{month:02d}", "D": f"{day:02d}", "Y": f"{year:04d}"}
        return "".join(parts[c] for c in pattern)
    out = pattern.replace("YYYY", f"{year:04d}").replace("YY", f"{year % 100:02d}")
    return out.replace("MM", f"{month:02d}").replace("DD", f"{day:02d}")
