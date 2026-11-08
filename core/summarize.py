"""Instant summary of a transcript, without a language model.

Picks the sentences that best represent the whole text (a TextRank style score:
a sentence ranks high when it shares words with many other sentences), keeps
them in their original order, and adds the action items found with the same
rules as meeting notes. Pure Python, offline, instant, and it works in any
language the app transcribes, since it only compares words. It quotes the
transcript; it never writes new sentences, so it cannot invent facts.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from core.meeting_notes import _ACTION, _NOT_AN_ACTION, _ONLY_THE_CUE

LENGTHS = {"short": 0.15, "medium": 0.3}
MIN_SENTENCES = 4  # below this there is nothing to shorten
MIN_POINTS = 2
MAX_POINTS = 12
MAX_ACTIONS = 8
_ITERATIONS = 30
COMMON_SHARE = 0.12
MIN_COMMON = 8
_DAMPING = 0.85

# Sentence ends: Latin and Arabic marks, CJK full stops, or a line break.
_SPLIT = re.compile(r"(?<=[.!?؟۔。！？])\s+|\n+")
_WORD = re.compile(r"\w+", re.UNICODE)
# Lines the app itself writes into the transcript box, not speech.
_APP_LINE = re.compile(
    r"^\s*(?:Downloaded to |Free (?:batch|link) |Last free |Batch (?:done|stopped)"
    r"|(?:done|failed|skipped|not run|saved|review): |could not label speakers"
    r"|Save \.srt captions was turned on)"
)
# The label in front of a transcribed file or link ("[talk.mp3] ..."), and the
# note in front of a site's own captions. Removed so the speech after it counts.
_LABEL = re.compile(
    r"^\s*\[(?:[^\[\]]|\[[^\]]*\])*\]\s*"  # may hold one inner pair: "[Title [id]]"
    r"(?:\(the site's own captions, may contain mistakes\)\s*)?"
)
# What is left when a line was only an app note: "[error] ...", "[no speech ...]".
_NOTE_ONLY = re.compile(r"^\s*\[[^\]]*\]")
_STOP = frozenset(
    """a an the and or but if then so of to in on at by for with from as is are was were be been
    being it its this that these those i you he she we they me him her us them my your his our
    their do does did have has had not no yes just very really also there here what which who
    when where how than too can could would should will shall may might must about into over
    up down out um uh like okay ok yeah well""".split()
)


@dataclass
class Summary:
    points: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    sentence_count: int = 0

    def is_empty(self) -> bool:
        return not self.points and not self.actions

    def as_text(self) -> str:
        parts: list[str] = []
        if self.points:
            parts.append("Summary")
            parts += [f"- {p}" for p in self.points]
        if self.actions:
            if parts:
                parts.append("")
            parts.append("Action items")
            parts += [f"- {a}" for a in self.actions]
        return "\n".join(parts)


def sentences(text: str) -> list[str]:
    """The spoken sentences in `text`, skipping lines the app wrote itself."""
    kept_lines = []
    for line in text.splitlines():
        if _APP_LINE.match(line):
            continue
        line = _LABEL.sub("", line, count=1)
        if _NOTE_ONLY.match(line):
            continue
        kept_lines.append(line)
    found = []
    for piece in _SPLIT.split("\n".join(kept_lines)):
        piece = piece.strip()
        if len(_WORD.findall(piece)) >= 3:
            found.append(piece)
    return found


def _words(sentence: str) -> set[str]:
    words = (m.lower() for m in _WORD.findall(sentence))
    return {w for w in words if w not in _STOP and len(w) > 1}


def rank(items: list[str]) -> list[float]:
    """A score per sentence: how central it is to the whole text."""
    bags = [_words(s) for s in items]
    n = len(items)
    # Only pairs that share a word can be linked, so find them through a word
    # index instead of comparing every pair: long meetings stay fast.
    index: dict[str, list[int]] = {}
    for i, bag in enumerate(bags):
        for word in bag:
            index.setdefault(word, []).append(i)
    # A word found in a large share of sentences says little about any one of
    # them (and linking through it is what makes long texts slow).
    too_common = max(MIN_COMMON, int(n * COMMON_SHARE)) if n > 60 else n
    shared: dict[tuple[int, int], int] = {}
    for holders in index.values():
        if len(holders) > too_common:
            continue
        for x, i in enumerate(holders):
            for j in holders[x + 1 :]:
                shared[(i, j)] = shared.get((i, j), 0) + 1
    sizes = [math.log(len(bag) + 1) for bag in bags]
    links: list[list[tuple[int, float]]] = [[] for _ in range(n)]
    totals = [0.0] * n
    for (i, j), count in shared.items():
        w = count / (sizes[i] + sizes[j])
        links[i].append((j, w))
        links[j].append((i, w))
        totals[i] += w
        totals[j] += w
    scores = [1.0] * n
    for _ in range(_ITERATIONS):
        new = [1 - _DAMPING] * n
        for j in range(n):
            if totals[j]:
                share = _DAMPING * scores[j] / totals[j]
                for i, w in links[j]:
                    new[i] += w * share
        scores = new
    return scores


def point_count(total: int, length: str) -> int:
    ratio = LENGTHS.get(length, LENGTHS["short"])
    return max(MIN_POINTS, min(MAX_POINTS, round(total * ratio)))


def _is_action(sentence: str) -> bool:
    return (
        not sentence.endswith("?")
        and bool(_ACTION.search(sentence))
        and not _NOT_AN_ACTION.search(sentence)
        and not _ONLY_THE_CUE.fullmatch(sentence)
    )


def summarize(text: str, length: str = "short") -> Summary:
    """Key sentences in their original order, plus action items."""
    items = sentences(text)
    summary = Summary(sentence_count=len(items))
    if len(items) < MIN_SENTENCES:
        return summary
    scores = rank(items)
    count = point_count(len(items), length)
    best = sorted(range(len(items)), key=lambda i: (-scores[i], i))[:count]
    summary.points = [items[i] for i in sorted(best)]
    summary.actions = [s for s in items if _is_action(s)][:MAX_ACTIONS]
    return summary
