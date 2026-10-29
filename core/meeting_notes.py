"""Builds the meeting note: a markdown file with the date, the length, action
items, decisions, open questions and the full transcript with times and speakers.

The action items, decisions and questions are found with plain rules (phrases such
as "I will", "we need to", "by Friday", "we decided"), not by a model. That keeps
everything offline and predictable, and it means the lists are a draft to edit,
not a finished summary. Every item carries its time and speaker so it can be
checked against the transcript.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from core.meeting import Line

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_DAY = r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
_ACTION = re.compile(
    r"\b(?:action items?|to-?do|follow(?:ing)?[ -]up|deadline|remind me|make sure|"
    r"don'?t forget|please (?:send|share|review|check|update|call|email|schedule)|"
    r"can you (?:send|share|review|check|update|call|email|schedule)|"
    r"i(?:'ll| will)|we(?:'ll| will)|you(?:'ll| will)|they(?:'ll| will)|"
    r"[A-Z][a-z]+ will|need(?:s)? to|have to|has to|should|must|let'?s|going to|"
    rf"due (?:on|by|date)|by (?:the )?(?:end of (?:the )?(?:day|week|month)|eod|tomorrow|"
    rf"tonight|next week|next month|{_DAY}))\b",
    re.IGNORECASE,
)
_NOT_AN_ACTION = re.compile(
    r"\b(?:will (?:be|see|say|probably|depend|work|talk|show)|should be|"
    r"must be|going to be)\b",
    re.IGNORECASE,
)
_DECISION = re.compile(
    r"\b(?:we(?:'ve)? (?:decided|agreed)|decided to|agreed to|the decision is|"
    r"final decision|let'?s go with|we(?:'re| are| will|'ll) go(?:ing)? with|"
    r"it'?s approved|approved)\b",
    re.IGNORECASE,
)
_ONLY_THE_CUE = re.compile(r"(?:action items?|to-?do|follow[ -]?up)[.:!]?", re.IGNORECASE)
MAX_QUESTIONS = 8
MIN_QUESTION_WORDS = 4


def clock(seconds: float) -> str:
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def _sentences(lines: list[Line]) -> list[tuple[Line, str]]:
    found: list[tuple[Line, str]] = []
    for line in lines:
        for sentence in _SENTENCE_SPLIT.split(line.text):
            sentence = sentence.strip()
            if sentence:
                found.append((line, sentence))
    return found


def _item(line: Line, sentence: str) -> str:
    return f"{sentence} ({clock(line.start)}, {line.speaker})"


def action_items(lines: list[Line]) -> list[str]:
    return [
        _item(line, sentence)
        for line, sentence in _sentences(lines)
        if not sentence.endswith("?")
        and _ACTION.search(sentence)
        and not _NOT_AN_ACTION.search(sentence)
        and not _ONLY_THE_CUE.fullmatch(sentence)
    ]


def decisions(lines: list[Line]) -> list[str]:
    return [
        _item(line, sentence)
        for line, sentence in _sentences(lines)
        if _DECISION.search(sentence) and not sentence.endswith("?")
    ]


def questions(lines: list[Line]) -> list[str]:
    found = [
        _item(line, sentence)
        for line, sentence in _sentences(lines)
        if sentence.endswith("?") and len(sentence.split()) >= MIN_QUESTION_WORDS
    ]
    return found[:MAX_QUESTIONS]


def title_for(started: datetime) -> str:
    return f"Meeting {started.strftime('%Y-%m-%d %H:%M')}"


def build_note(
    lines: list[Line], started: datetime, seconds: float, with_others: bool = True
) -> str:
    """The note as markdown. `with_others` is False for a microphone-only meeting."""
    minutes = max(1, round(seconds / 60))
    speakers = sorted({line.speaker for line in lines}, key=lambda s: (s != "You", s))
    out = [
        "---",
        "tags: [meeting]",
        f"date: {started.strftime('%Y-%m-%d')}",
        f"duration: {minutes} min",
        "---",
        f"# {title_for(started)}",
        "",
        f"**Date:** {started.strftime('%Y-%m-%d %H:%M')}  ",
        f"**Length:** {minutes} min  ",
        f"**Speakers:** {', '.join(speakers) if speakers else 'none heard'}",
    ]
    if not with_others:
        out.append("")
        out.append("*Recorded on the microphone only.*")
    if not lines:
        out += ["", "No speech was recognized in this recording."]
        return "\n".join(out) + "\n"
    out += ["", "## Action items", ""]
    items = action_items(lines)
    out += [f"- [ ] {item}" for item in items] or ["- none found"]
    out += ["", "## Decisions", ""]
    out += [f"- {item}" for item in decisions(lines)] or ["- none found"]
    open_questions = questions(lines)
    if open_questions:
        out += ["", "## Questions", ""]
        out += [f"- {item}" for item in open_questions]
    out += ["", "## Transcript", ""]
    out += [f"**[{clock(line.start)}] {line.speaker}:** {line.text}" for line in lines]
    out += ["", "*Made on this PC by VoxScribe. Action items and decisions are found by "
            "simple rules, so check them against the transcript.*"]
    return "\n".join(out) + "\n"


def save_note(folder: Path, note: str, started: datetime) -> Path:
    """Writes the note into `folder` (created when missing) without overwriting an
    existing file of the same name."""
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"{started.strftime('%Y-%m-%d %H-%M')} Meeting"
    path = folder / f"{stem}.md"
    counter = 2
    while path.exists():
        path = folder / f"{stem} ({counter}).md"
        counter += 1
    path.write_text(note, encoding="utf-8", newline="\n")
    return path
