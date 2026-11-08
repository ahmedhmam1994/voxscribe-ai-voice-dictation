"""Learns your words: when you fix a word VoxScribe typed ("Shivon" to
"Siobhan"), the fix is kept and made for you from then on, like a word
replacement you never had to write. The Windows side of the Android app's
LearnedWords.kt, with the same rules so both learn the same way.

Only a clear spelling fix is learned: one word swapped for a similar one
(same first sound, mostly the same letters), a casing fix ("voxscribe" to
"VoxScribe") or two words joined ("vox scribe" to "VoxScribe"). Changing
what you meant ("Tuesday" to "Wednesday") is never learned, because
everyday words (core/data/common_words.txt) are left out on both sides.

Where fixes come from (app/main_window.py): a word you fix in the app you
dictated into, read back through UI Automation (core/focused_text.py), and
Try harder changing a word. Kept on this PC only; each learned fix can be
removed on the My words page.
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QSettings

from core.term_packs import _soft

MAX = 200
MIN_RATIO = 0.4
COMMON_WORDS_PATH = Path(__file__).parent / "data" / "common_words.txt"

_WORD = re.compile(r"[^\W_]+(?:['’][^\W\d_]+)?")
_SUFFIXES = ("s", "es", "ed", "ing", "er", "ers", "ly", "ies", "ied")


@dataclass(frozen=True)
class Fix:
    heard: str
    fixed: str


# -- the everyday words -------------------------------------------------------


@lru_cache(maxsize=1)
def common_words() -> frozenset[str]:
    """About 20,000 everyday lowercase words. Empty when the file is missing,
    which turns learning off rather than guessing."""
    try:
        lines = COMMON_WORDS_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return frozenset()
    return frozenset(line.strip() for line in lines if line.strip() and not line.startswith("#"))


def is_common(lower: str, common: frozenset[str] | set[str]) -> bool:
    """`lower` or a plain form of it ("archived", "dictating") is an everyday word."""
    if lower in common:
        return True
    for suffix in _SUFFIXES:
        if not lower.endswith(suffix) or len(lower) - len(suffix) < 3:
            continue
        stem = lower[: -len(suffix)]
        if stem in common or stem + "e" in common:
            return True
        if suffix.startswith("i") and stem + "y" in common:
            return True
        # "running" to "run".
        if len(stem) >= 3 and stem[-1] == stem[-2] and stem[:-1] in common:
            return True
    return False


# -- spotting a fix -------------------------------------------------------------


def find_fix(
    before: str, after: str, dictated_from: int = 0, common: frozenset[str] | set[str] | None = None
) -> Fix | None:
    """The spelling fix that turned `before` (the box as VoxScribe left it)
    into `after` (the box now), or None. Only words from `dictated_from` on
    count: VoxScribe learns from what it typed, not from what was there."""
    if common is None:
        common = common_words()
    if not common:
        return None
    old = list(_WORD.finditer(before))
    new = list(_WORD.finditer(after))
    head = 0
    while head < len(old) and head < len(new) and old[head].group() == new[head].group():
        head += 1
    tail = 0
    while (
        tail < len(old) - head
        and tail < len(new) - head
        and old[len(old) - 1 - tail].group() == new[len(new) - 1 - tail].group()
    ):
        tail += 1
    changed = old[head : len(old) - tail]
    typed = new[head : len(new) - tail]
    if not changed or len(changed) > 2 or len(typed) != 1:
        return None
    if changed[0].start() < dictated_from:
        return None
    fixed = typed[0].group()
    heard = " ".join(w.group() for w in changed)
    if len(fixed) < 2 or not fixed.isalpha() or any(not w.group().isalpha() for w in changed):
        return None
    fixed_lower = fixed.lower()
    if is_common(fixed_lower, common):
        return None
    if len(changed) == 2:
        # "vox scribe" to "VoxScribe": the same letters, joined.
        return Fix(heard, fixed) if heard.replace(" ", "").lower() == fixed_lower else None
    heard_lower = heard.lower()
    if heard == fixed or is_common(heard_lower, common):
        return None
    if heard_lower == fixed_lower:
        return Fix(heard, fixed)
    same_start = heard_lower[0] == fixed_lower[0] or _soft(heard_lower[0], fixed_lower[0])
    ratio = difflib.SequenceMatcher(None, heard_lower, fixed_lower).ratio()
    if not same_start or ratio < MIN_RATIO:
        return None
    return Fix(heard, fixed)


def _learned_as(fixes: list[Fix], fix: Fix) -> Fix:
    chained = next((f for f in fixes if f.fixed.lower() == fix.heard.lower()), None)
    return Fix(chained.heard, fix.fixed) if chained else fix


def add(fixes: list[Fix], fix: Fix) -> list[Fix]:
    """`fixes` with `fix` added last. A fix for the same words, or one that
    undoes it, goes. A fix of a learned fix ("Shivon" to "Sio", then "Sio"
    finished to "Siobhan") becomes one fix from the first words."""
    learned = _learned_as(fixes, fix)
    kept = [
        f
        for f in fixes
        if f.heard.lower() != learned.heard.lower() and f.heard.lower() != learned.fixed.lower()
    ]
    # Fixing a learned word back to what was heard just forgets it.
    if learned.heard == learned.fixed:
        return kept
    return (kept + [learned])[-MAX:]


# -- kept on this PC -----------------------------------------------------------


def _settings() -> QSettings:
    return QSettings("VoxScribe", "VoxScribe")


def get_enabled() -> bool:
    """Default on, like on Android."""
    return str(_settings().value("learn_fixes", "true")).lower() == "true"


def set_enabled(enabled: bool) -> None:
    _settings().setValue("learn_fixes", "true" if enabled else "false")


def all_fixes() -> list[Fix]:
    raw = _settings().value("learned_words", "")
    try:
        pairs = json.loads(raw) if raw else []
    except ValueError:
        return []
    return [
        Fix(a, b)
        for a, b in (p for p in pairs if isinstance(p, list) and len(p) == 2)
        if isinstance(a, str) and isinstance(b, str) and a.strip()
    ]


def _save(fixes: list[Fix]) -> None:
    _settings().setValue("learned_words", json.dumps([[f.heard, f.fixed] for f in fixes]))


def remember(fix: Fix) -> Fix | None:
    """Keeps `fix` and returns it as learned (see add), or None when it only
    undid a learned fix."""
    fixes = all_fixes()
    _save(add(fixes, fix))
    learned = _learned_as(fixes, fix)
    return learned if learned.heard != learned.fixed else None


def forget(heard: str) -> None:
    _save([f for f in all_fixes() if f.heard.lower() != heard.lower()])


def clear() -> None:
    _save([])


def pairs() -> list[tuple[str, str]]:
    """The learned fixes as replacement pairs, or none when learning is off."""
    if not get_enabled():
        return []
    return [(f.heard, f.fixed) for f in all_fixes()]
