"""Teach VoxScribe your voice: finds the words the speech model gets wrong for
one speaker (an accent, a habit) so they can be fixed from then on.

The person reads a short script. Every sentence is written around a few known
terms (drug names, legal words, business words, or their own vocabulary). After
each sentence is transcribed, this module compares what was heard with what was
meant, looks only at the known terms, and proposes a replacement for each one
that came out differently ("levoseroxine" -> "levothyroxine"). Nothing is
applied until the person ticks it, because a replacement changes that word
everywhere they dictate.

Pure logic with no audio or UI, so it is easy to test.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

# pack id -> [(sentence, terms the sentence is about)]. Every term is a term of
# that pack (tests/test_voice_teach.py checks it).
SENTENCES: dict[str, list[tuple[str, list[str]]]] = {
    "medical": [
        (
            "She was prescribed amlodipine and atorvastatin for high blood pressure.",
            ["amlodipine", "atorvastatin"],
        ),
        ("The doctor ordered a CBC, an HbA1c and a chest X-ray.", ["CBC", "HbA1c", "X-ray"]),
        (
            "He takes omeprazole in the morning and gabapentin at night.",
            ["omeprazole", "gabapentin"],
        ),
        (
            "The ultrasound showed gallstones, so they scheduled a cholecystectomy.",
            ["cholecystectomy"],
        ),
        (
            "Her TSH was high, so she started levothyroxine for hypothyroidism.",
            ["TSH", "levothyroxine", "hypothyroidism"],
        ),
        (
            "The patient has atrial fibrillation and takes apixaban and bisoprolol.",
            ["atrial fibrillation", "apixaban", "bisoprolol"],
        ),
        (
            "He was given amoxicillin for the infection and ibuprofen for the pain.",
            ["amoxicillin", "ibuprofen"],
        ),
        ("The biopsy ruled out carcinoma, and the MRI showed no stroke.", ["carcinoma", "MRI"]),
    ],
    "legal": [
        (
            "The plaintiff filed a motion for summary judgment before the deposition.",
            ["plaintiff", "summary judgment", "deposition"],
        ),
        (
            "Please sign the NDA before we discuss the indemnification clause.",
            ["NDA", "indemnification"],
        ),
        (
            "The lawyer cited habeas corpus and the statute of limitations.",
            ["habeas corpus", "statute of limitations"],
        ),
        (
            "The defendant received a subpoena and an affidavit from the court.",
            ["defendant", "subpoena", "affidavit"],
        ),
        (
            "The fiduciary signed the power of attorney before the arbitration.",
            ["fiduciary", "power of attorney", "arbitration"],
        ),
        ("The buyer asked about the lien and the escrow account.", ["lien", "escrow"]),
        ("The injunction was granted ex parte pending the hearing.", ["injunction", "ex parte"]),
        (
            "The testator named an executor and a beneficiary in the codicil.",
            ["testator", "executor", "beneficiary", "codicil"],
        ),
    ],
    "business": [
        ("Our EBITDA grew this quarter, and the KPI report is due Friday.", ["EBITDA", "KPI"]),
        ("The client wants to renew the SLA before the end of Q3.", ["SLA", "Q3"]),
        ("We are tracking CAC, ARR and churn for the board meeting.", ["CAC", "ARR", "churn"]),
        (
            "The SaaS startup raised a seed round from an angel investor.",
            ["SaaS", "seed round", "angel investor"],
        ),
        (
            "Her OKR is to improve the NPS and the conversion rate.",
            ["OKR", "NPS", "conversion rate"],
        ),
        (
            "The CFO reviewed the balance sheet and the cash flow forecast.",
            ["CFO", "balance sheet", "cash flow"],
        ),
        ("We signed the term sheet and started due diligence.", ["term sheet", "due diligence"]),
        (
            "The B2B pipeline depends on the go-to-market plan and the roadmap.",
            ["B2B", "pipeline", "go-to-market", "roadmap"],
        ),
    ],
}

DEFAULT_LENGTH = 10
_MAX_CUSTOM_TERMS = 4

# Words that are never worth a replacement on their own.
_STOPWORDS = frozenset(
    "a an and are as at be but by for from had has have he her his i in is it its of on or "
    "she that the their them then there they this to was we were will with you your".split()
)
_WORD = re.compile(r"[\w'’]+")


@dataclass(frozen=True)
class Slip:
    heard: str
    expected: str


@dataclass
class Proposal:
    heard: str
    expected: str
    count: int = 1


def build_script(enabled: list[str], custom: list[str], length: int = DEFAULT_LENGTH):
    """[(sentence, terms)] to read: the enabled packs take turns, so each is
    represented; with none enabled, the built-in packs are used. A sentence about
    the person's own vocabulary comes last."""
    packs = [p for p in enabled if p in SENTENCES] or list(SENTENCES)
    script: list[tuple[str, list[str]]] = []
    custom_terms = [t for t in custom if t.strip()][:_MAX_CUSTOM_TERMS]
    room = length - (1 if custom_terms else 0)
    index = 0
    while len(script) < room and any(index < len(SENTENCES[p]) for p in packs):
        for pack in packs:
            if index < len(SENTENCES[pack]) and len(script) < room:
                script.append(SENTENCES[pack][index])
        index += 1
    if custom_terms:
        script.append((f"Today I will talk about {_join(custom_terms)}.", custom_terms))
    return script


def _join(terms: list[str]) -> str:
    if len(terms) == 1:
        return terms[0]
    return ", ".join(terms[:-1]) + " and " + terms[-1]


def _words(text: str) -> list[str]:
    """Lowercase words; a hyphen separates words, so "X-ray" and "X ray" match."""
    return _WORD.findall(text.lower().replace("-", " "))


def _find(haystack: list[str], needle: list[str]) -> int:
    for start in range(len(haystack) - len(needle) + 1):
        if haystack[start : start + len(needle)] == needle:
            return start
    return -1


def find_slips(
    sentence: str, targets: list[str], heard: str, known_terms: list[str] | None = None
) -> list[Slip]:
    """The targets of `sentence` that `heard` has written differently. A target
    is judged only when the words around it were heard right, so one garbled
    stretch is not mistaken for several slips. A heard phrase that is itself a
    known term is never proposed (that would turn a correct word into another)."""
    expected = _words(sentence)
    got = _words(heard)
    if not got:
        return []
    known = {" ".join(_words(t)) for t in (known_terms or [])}
    matcher = difflib.SequenceMatcher(None, expected, got, autojunk=False)
    heard_of: dict[int, int] = {}
    for block in matcher.get_matching_blocks():
        for offset in range(block.size):
            heard_of[block.a + offset] = block.b + offset
    slips: list[Slip] = []
    for target in targets:
        words = _words(target)
        start = _find(expected, words)
        if start < 0:
            continue
        end = start + len(words)
        if all(i in heard_of for i in range(start, end)):
            continue  # heard right
        left = start - 1
        if left >= 0 and left not in heard_of:
            continue
        if end < len(expected) and end not in heard_of:
            continue
        span_start = heard_of[left] + 1 if left >= 0 else 0
        span_end = heard_of[end] if end < len(expected) else len(got)
        span = got[span_start:span_end]
        if not span or len(span) > len(words) + 2:
            continue
        phrase = " ".join(span)
        if phrase == " ".join(words) or phrase in known:
            continue
        if len(phrase) < 3 or all(w in _STOPWORDS for w in span):
            continue
        slips.append(Slip(phrase, target))
    return slips


def merge(slip_lists: list[list[Slip]]) -> list[Proposal]:
    """One proposal per distinct (heard, expected), most repeated first."""
    seen: dict[tuple[str, str], Proposal] = {}
    for slips in slip_lists:
        for slip in slips:
            key = (slip.heard, slip.expected.lower())
            if key in seen:
                seen[key].count += 1
            else:
                seen[key] = Proposal(slip.heard, slip.expected)
    return sorted(seen.values(), key=lambda p: (-p.count, p.expected.lower()))
