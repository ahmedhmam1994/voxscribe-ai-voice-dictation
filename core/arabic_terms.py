"""English words that Arabic dictation writes in Arabic letters, turned back.

Every speech model tested here writes an English word spoken inside an Arabic
sentence in Arabic letters ("ميتنج" for "meeting", "ريبورت" for "report"). This
is a small, fixed list of common work words that fixes the most frequent ones.
It is a plain word-for-word swap, fully offline and predictable: only whole
words on the list change, and only when the text contains Arabic letters. A
word that is also a real Arabic word (such as "اب", father, for "app") is left
out on purpose.

With the definite article ("الميتنج") the result keeps the usual way of writing
it in mixed text: "الـ meeting".
"""

from __future__ import annotations

import re

# English word -> the spellings the models give it in Arabic letters.
_TERMS: dict[str, tuple[str, ...]] = {
    "meeting": ("ميتنج", "ميتينج", "ميتنغ", "ميتينغ", "ميتنك"),
    "report": ("ريبورت", "ربورت", "ريبورد", "ريبورتر"),
    "client": ("كلاينت", "كلينت", "كلايينت", "كلاينتس"),
    "launch": ("لونش", "لانش", "لونج", "لانتش", "لونتش"),
    "update": ("ابدات", "ابديت", "أبديت", "أبدات", "ابداتس"),
    "pricing": ("برايسينج", "برايسنج", "برايسينغ", "بريسينج", "برايسنغ"),
    "email": ("ايميل", "إيميل", "اميل", "ايمايل"),
    "link": ("لينك", "لنك"),
    "file": ("فايل", "فيل"),
    "deadline": ("ديدلاين", "ديدلين"),
    "project": ("بروجكت", "بروجيكت", "بروجكتس"),
    "team": ("تيم", "تيمز"),
    "design": ("ديزاين", "ديزين", "دزاين"),
    "server": ("سيرفر", "سرفر"),
    "data": ("داتا", "ديتا"),
    "demo": ("ديمو",),
    "feedback": ("فيدباك", "فيد باك"),
    "profile": ("بروفايل", "بروفيل"),
    "application": ("ابليكيشن", "أبليكيشن", "ابلكيشن", "أبلكيشن"),
    "online": ("اونلاين", "أونلاين", "أون لاين"),
    "offline": ("اوفلاين", "أوفلاين"),
    "order": ("اوردر", "أوردر", "اورد"),
    "message": ("ميسج", "ميساج", "ماسج"),
    "password": ("باسوورد", "باسورد", "باسوورد"),
    "software": ("سوفتوير", "سوفت وير"),
    "website": ("ويبسايت", "ويب سايت"),
}

_DIACRITICS = re.compile("[ً-ٰٟـ]")
_ARABIC_TOKEN = re.compile("[ء-يٱ-ۓً-ٟـ]+")
_HAS_ARABIC = re.compile("[؀-ۿ]")
_ARTICLE = "ال"  # ال
_TATWEEL = "ـ"


def _key(word: str) -> str:
    """Spelling variants that people and models mix up compare equal."""
    word = _DIACRITICS.sub("", word)
    for src in "أإآ":
        word = word.replace(src, "ا")
    return word.replace("ى", "ي").replace("ة", "ه")


_LOOKUP: dict[str, str] = {
    _key(spelling): english for english, spellings in _TERMS.items() for spelling in spellings
}


def apply_arabic_terms(text: str) -> str:
    """Swaps listed Arabic-letter spellings for the English word."""
    if not _HAS_ARABIC.search(text):
        return text

    def swap(match: re.Match[str]) -> str:
        token = match.group(0)
        key = _key(token)
        if key in _LOOKUP:
            return _LOOKUP[key]
        if key.startswith(_ARTICLE) and key[len(_ARTICLE) :] in _LOOKUP:
            return f"{_ARTICLE}{_TATWEEL} {_LOOKUP[key[len(_ARTICLE) :]]}"
        return token

    return _ARABIC_TOKEN.sub(swap, text)
