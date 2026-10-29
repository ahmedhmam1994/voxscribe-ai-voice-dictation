"""Term packs: ready-made word lists for a field (medical, law, business) and
the user's own list files, plus the step that fixes how those words are written.

A pack is a plain text file, one term per line (lines starting with # are
notes). Three packs ship inside the app; a user can import their own file, for
example a clinic's drug list or a firm's client names, and it is kept in the
app's folder. Everything is local: no pack is ever downloaded.

Two things use the enabled packs together with the custom vocabulary:

* a short hint for Whisper (its initial prompt), which only Whisper understands
  and which is limited in length, so the first terms of each pack are the ones
  that matter most;
* a correction pass over the finished text, which works for every speech model:
  it fixes the casing of a listed word ("mri" -> "MRI"), joins a word the model
  split in two ("met formin" -> "metformin") and, for the rare words a pack marks
  as safe for it (drug names), repairs a misspelling or a same-sounding spelling
  ("lisinipril", "lezenobril" -> "lisinopril"). Ordinary words are never repaired
  this way, since "expression" is one slip from "depression".

A pack file may hold the line "# fuzzy: on" before such rare terms and
"# fuzzy: off" after them. Without those lines a term only gets its casing fixed.
"""

from __future__ import annotations

import difflib
import os
import re
from functools import lru_cache
from pathlib import Path

BUILTIN_DIR = Path(__file__).parent / "packs"
USER_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "VoxScribe" / "packs"

# (id, label) of the packs that ship with the app.
BUILTIN_PACKS: tuple[tuple[str, str], ...] = (
    ("medical", "Medical"),
    ("legal", "Law"),
    ("business", "Business"),
)
USER_PREFIX = "user:"

MAX_TERMS = 6000
MAX_TERM_LENGTH = 60
MAX_FILE_BYTES = 1_000_000
PROMPT_CHARS = 450
_MAX_PHRASE_WORDS = 4
_MIN_JOINED = 7
_MIN_FUZZY = 8
_LONG = 9
_FUZZY_RATIO = 0.9
_ANCHOR_RATIO = 0.84
_GAP_RATIO = 0.88
_SWAP_COST = 0.5
_SOUND_DISTANCE = 1.6
_MARGIN = 0.3

_TOKEN = re.compile(r"[A-Za-z0-9]+(?:['’\-][A-Za-z0-9]+)*")


def parse_pack(text: str) -> tuple[list[str], list[str]]:
    """(terms, fuzzy terms) in a pack file: no blanks or notes, no repeats (any
    case). The fuzzy terms are those between "# fuzzy: on" and "# fuzzy: off"."""
    terms: list[str] = []
    fuzzy: list[str] = []
    seen: set[str] = set()
    fuzzy_on = False
    for line in text.lstrip("﻿").splitlines():
        term = " ".join(line.split())
        if term.lower() in ("# fuzzy: on", "# fuzzy: off"):
            fuzzy_on = term.lower().endswith("on")
            continue
        if not term or term.startswith("#") or len(term) > MAX_TERM_LENGTH:
            continue
        if term.lower() in seen:
            continue
        seen.add(term.lower())
        terms.append(term)
        if fuzzy_on:
            fuzzy.append(term)
        if len(terms) >= MAX_TERMS:
            break
    return terms, fuzzy


def parse_pack_text(text: str) -> list[str]:
    return parse_pack(text)[0]


@lru_cache(maxsize=32)
def _read(path: str, mtime_ns: int) -> tuple[tuple[str, ...], tuple[str, ...]]:
    terms, fuzzy = parse_pack(Path(path).read_text(encoding="utf-8", errors="replace"))
    return tuple(terms), tuple(fuzzy)


def _pack_path(pack_id: str) -> Path | None:
    if pack_id.startswith(USER_PREFIX):
        name = pack_id[len(USER_PREFIX) :]
        path = USER_DIR / f"{name}.txt"
    elif any(pack_id == known for known, _ in BUILTIN_PACKS):
        path = BUILTIN_DIR / f"{pack_id}.txt"
    else:
        return None
    return path if path.is_file() else None


def _pack(pack_id: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    path = _pack_path(pack_id)
    if path is None:
        return (), ()
    try:
        return _read(str(path), path.stat().st_mtime_ns)
    except OSError:
        return (), ()


def pack_terms(pack_id: str) -> list[str]:
    return list(_pack(pack_id)[0])


def pack_fuzzy_terms(pack_id: str) -> list[str]:
    return list(_pack(pack_id)[1])


def available_packs() -> list[tuple[str, str, int]]:
    """(id, label, number of terms) for the built-in packs and the user's own."""
    packs = [(pack_id, label, len(pack_terms(pack_id))) for pack_id, label in BUILTIN_PACKS]
    if USER_DIR.is_dir():
        for path in sorted(USER_DIR.glob("*.txt")):
            pack_id = f"{USER_PREFIX}{path.stem}"
            packs.append((pack_id, path.stem, len(pack_terms(pack_id))))
    return [pack for pack in packs if pack[2] > 0]


def import_pack(source: Path) -> tuple[str, str, int]:
    """Copies a term file into the app's folder. Returns (id, label, terms).
    Raises ValueError for a file that is too big or holds no terms."""
    if source.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("That file is too big for a term pack (1 MB at most).")
    text = source.read_text(encoding="utf-8", errors="replace")
    terms = parse_pack_text(text)
    if not terms:
        raise ValueError("No terms found. A pack is a text file with one term per line.")
    name = re.sub(r"[^\w \-]", "", source.stem).strip()[:40] or "My pack"
    USER_DIR.mkdir(parents=True, exist_ok=True)
    (USER_DIR / f"{name}.txt").write_text(text, encoding="utf-8")
    return f"{USER_PREFIX}{name}", name, len(terms)


def remove_user_pack(pack_id: str) -> bool:
    if not pack_id.startswith(USER_PREFIX):
        return False
    path = _pack_path(pack_id)
    if path is None:
        return False
    try:
        path.unlink()
    except OSError:
        return False
    return True


def combined_terms(enabled: list[str], custom: list[str]) -> list[str]:
    """Custom vocabulary first, then each enabled pack in order, no repeats."""
    seen: set[str] = set()
    terms: list[str] = []
    for term in [*custom, *(t for pack_id in enabled for t in pack_terms(pack_id))]:
        if term.lower() not in seen:
            seen.add(term.lower())
            terms.append(term)
    return terms[:MAX_TERMS]


def combined_fuzzy_terms(enabled: list[str]) -> list[str]:
    """The terms of the enabled packs that may be repaired when misspelled."""
    return [t for pack_id in enabled for t in pack_fuzzy_terms(pack_id)]


def hint_prompt(enabled: list[str], custom: list[str]) -> str | None:
    """Whisper's initial prompt: the custom vocabulary in full, then as many
    pack terms as fit, taking the first of each pack so that every enabled pack
    is represented."""
    parts = [t.strip() for t in custom if t.strip()]
    seen = {t.lower() for t in parts}
    per_pack = [pack_terms(pack_id) for pack_id in enabled]
    length = sum(len(t) + 2 for t in parts)
    index = 0
    while any(index < len(terms) for terms in per_pack):
        for terms in per_pack:
            if index >= len(terms):
                continue
            term = terms[index]
            if term.lower() in seen or (" " in term and len(term) > 24):
                continue
            if length + len(term) + 2 > PROMPT_CHARS:
                return _sentence(parts)
            seen.add(term.lower())
            parts.append(term)
            length += len(term) + 2
        index += 1
    return _sentence(parts)


def _sentence(parts: list[str]) -> str | None:
    return "Vocabulary that may come up: " + ", ".join(parts) + "." if parts else None


_SOFT_PAIRS = [
    set("aeiou"), set("bp"), set("dt"), set("gk"), set("sz"), set("fv"), set("ck"), set("cs"),
]  # fmt: skip
_VOWELS = set("aeiou")


def _soft(a: str, b: str) -> bool:
    return any(a in group and b in group for group in _SOFT_PAIRS)


def _substitution_cost(a: str, b: str) -> float:
    if a == b:
        return 0.0
    if a in _VOWELS and b in _VOWELS:
        return 0.25
    return 0.4 if _soft(a, b) else 1.0


def _gap_cost(ch: str) -> float:
    return 0.6 if ch in _VOWELS else 1.0


def _sound_distance(a: str, b: str) -> float:
    """Edit distance in which look-alike sounds (vowel for vowel, b/p, d/t, g/k,
    s/z, f/v), a missing vowel and two neighbouring letters swapped cost little.
    "lezenobril" is 1.6 from "lisinopril" and "atrovastatine" 1.1 from
    "atorvastatin", while "permission" is far from "percussion"."""
    rows = [[0.0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for j, ch in enumerate(b, 1):
        rows[0][j] = rows[0][j - 1] + _gap_cost(ch)
    for i, ch_a in enumerate(a, 1):
        rows[i][0] = rows[i - 1][0] + _gap_cost(ch_a)
        for j, ch_b in enumerate(b, 1):
            best = min(
                rows[i - 1][j - 1] + _substitution_cost(ch_a, ch_b),
                rows[i - 1][j] + _gap_cost(ch_a),
                rows[i][j - 1] + _gap_cost(ch_b),
            )
            if i > 1 and j > 1 and ch_a == b[j - 2] and a[i - 2] == ch_b:
                best = min(best, rows[i - 2][j - 2] + _SWAP_COST)
            rows[i][j] = best
    return rows[-1][-1]


def _closeness(word: str, term: str) -> float | None:
    """How far `word` is from `term` when it is a clear mishearing of it (lower
    is closer), else None. Both are lowercase."""
    gap = abs(len(word) - len(term))
    if gap > 2 or not (word[0] == term[0] or _soft(word[0], term[0])):
        return None
    ratio = difflib.SequenceMatcher(None, word, term).ratio()
    if gap == 2:
        # A syllable dropped ("amoxillin"): only for long words that start alike.
        if len(word) < _LONG - 1 or word[:4] != term[:4] or ratio < _GAP_RATIO:
            return None
        return 2.0 * (1.0 - ratio) * len(term)
    distance = _sound_distance(word, term)
    anchored = (
        len(word) >= _LONG
        and word[:3] == term[:3]
        and word[-3:] == term[-3:]
        and ratio >= _ANCHOR_RATIO
    )
    if ratio >= _FUZZY_RATIO or distance <= _SOUND_DISTANCE or anchored:
        return min(distance, 2.0 * (1.0 - ratio) * len(term))
    return None


class _Index:
    def __init__(self, terms: tuple[str, ...], fuzzy_terms: tuple[str, ...]) -> None:
        self.single: dict[str, str] = {}
        self.phrase: dict[str, str] = {}
        self.fuzzy: dict[str, str] = {}
        self.max_words = 1
        self.acronyms: dict[str, str] = {}
        for term in terms:
            words = term.split(" ")
            if len(words) == 1:
                self.single.setdefault(term.lower(), term)
                if term.isalpha() and term.isupper() and len(term) >= 2:
                    self.acronyms.setdefault(term.lower(), term)
                if "-" in term:
                    # "X ray" and "xray" for "X-ray": a model drops the hyphen.
                    self.phrase.setdefault(term.lower().replace("-", " "), term)
                    self.max_words = max(self.max_words, term.count("-") + 1)
            elif len(words) <= _MAX_PHRASE_WORDS:
                self.phrase.setdefault(term.lower(), term)
                self.max_words = max(self.max_words, len(words))
        for term in fuzzy_terms:
            if term.isalpha() and len(term) >= _MIN_FUZZY:
                self.fuzzy.setdefault(term.lower(), term)

    def near(self, token: str) -> str | None:
        """A fuzzy-safe listed word that the token is a clear mishearing of."""
        lower = token.lower()
        if not token.isalpha() or len(lower) < _MIN_FUZZY or lower in self.single:
            return None
        scored = []
        for candidate_lower, candidate in self.fuzzy.items():
            score = _closeness(lower, candidate_lower)
            if score is not None:
                scored.append((score, candidate))
        scored.sort()
        if not scored:
            return None
        # Two listed words equally close means a guess: leave the text alone.
        if len(scored) > 1 and scored[1][0] - scored[0][0] < _MARGIN:
            return None
        return scored[0][1]


@lru_cache(maxsize=4)
def _index(terms: tuple[str, ...], fuzzy_terms: tuple[str, ...]) -> _Index:
    return _Index(terms, fuzzy_terms)


def _like(original: str, canonical: str, text: str, start: int) -> str:
    """A lowercase term keeps a capital only at the start of a sentence: a model
    that writes "Azithromycin" in the middle of one gets "azithromycin"."""
    before = text[:start].rstrip(" \t")
    at_sentence_start = not before or before[-1] in ".!?\n"
    if canonical.islower() and original[:1].isupper() and at_sentence_start:
        return canonical[:1].upper() + canonical[1:]
    return canonical


def correct_text(text: str, terms: list[str], fuzzy_terms: list[str] | None = None) -> str:
    """Rewrites the words of `text` that match a listed term. Text without
    Latin letters (Arabic and so on) is left alone."""
    if not terms or not text:
        return text
    index = _index(tuple(terms), tuple(fuzzy_terms or ()))
    tokens = list(_TOKEN.finditer(text))
    out: list[str] = []
    cursor = 0
    i = 0
    while i < len(tokens):
        replaced = False
        longest = min(max(index.max_words, 3), len(tokens) - i)
        for size in range(longest, 0, -1):
            window = tokens[i : i + size]
            if any(text[a.end() : b.start()] != " " for a, b in zip(window, window[1:])):
                continue
            start, end = window[0].start(), window[-1].end()
            original = text[start:end]
            lower_words = [m.group(0).lower() for m in window]
            canonical = None
            if size >= 2:
                canonical = index.phrase.get(" ".join(lower_words))
                if canonical is None and all(len(w) == 1 for w in lower_words):
                    # Letters spelled out ("C A C") for a listed acronym.
                    canonical = index.acronyms.get("".join(lower_words))
                if canonical is None and size <= 3:
                    joined = "".join(lower_words)
                    if len(joined) >= _MIN_JOINED:
                        canonical = index.single.get(joined)
            else:
                canonical = index.single.get(lower_words[0]) or index.near(original)
            if canonical is None:
                continue
            canonical = _like(original, canonical, text, start)
            if canonical != original:
                out.append(text[cursor:start])
                out.append(canonical)
                cursor = end
            i += size
            replaced = True
            break
        if not replaced:
            i += 1
    out.append(text[cursor:])
    return "".join(out)
