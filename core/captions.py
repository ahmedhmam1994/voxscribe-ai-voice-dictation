"""Splits long transcript segments into caption cards that fit on screen.

Whisper returns whole segments, some of them long. Captions read best at
about 42 characters a line and two lines a card (the common broadcast and
YouTube guidance), so a long segment is cut into several cards. Times are
shared out by text length, since only segment level times are available.
Pure string logic with no Whisper dependency, like core/srt.py.
"""

from __future__ import annotations

Segment = tuple[float, float, str]

DEFAULT_LINE_CHARS = 42
MAX_LINES = 2
_CLAUSE_ENDS = ".?!;:,"


def _cut_point(text: str, limit: int) -> int:
    """Index to cut `text` at (a space), so the first part is at most `limit`
    characters, preferring the end of a sentence, then a clause, then a space."""
    window = text[: limit + 1]
    floor = limit * 2 // 5
    for ends in (".?!", ";:,"):
        best = -1
        for i, ch in enumerate(window):
            if ch in ends and i >= floor and (i + 1 == len(text) or text[i + 1] == " "):
                best = i + 1
        if best > 0:
            return best
    space = window.rfind(" ")
    if space > 0:
        return space
    after = text.find(" ", limit)
    return after if after > 0 else len(text)


def _chunks(text: str, limit: int) -> list[str]:
    """Cuts text into pieces of at most `limit` characters where it can."""
    pieces = []
    rest = text.strip()
    while len(rest) > limit:
        cut = _cut_point(rest, limit)
        pieces.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    if rest:
        pieces.append(rest)
    return pieces


def _two_lines(text: str, line_chars: int) -> str:
    """Breaks a card that is longer than one line into two balanced lines."""
    if len(text) <= line_chars:
        return text
    best = None
    for i, ch in enumerate(text):
        if ch != " ":
            continue
        first, second = text[:i], text[i + 1 :]
        score = abs(len(first) - len(second))
        if best is None or score < best[0]:
            best = (score, first, second)
    return text if best is None else f"{best[1]}\n{best[2]}"


def split_segments(
    segments: list[Segment], line_chars: int = DEFAULT_LINE_CHARS
) -> list[Segment]:
    """Returns caption cards: no card has more than two lines of `line_chars`.
    A `line_chars` of 0 or less leaves the segments as they are."""
    if line_chars <= 0:
        return list(segments)
    cards: list[Segment] = []
    for start, end, text in segments:
        text = " ".join(text.split())
        if not text:
            continue
        pieces = _chunks(text, line_chars * MAX_LINES)
        total = sum(len(p) for p in pieces)
        duration = max(end - start, 0.0)
        done = 0
        for piece in pieces:
            card_start = start + duration * done / total
            done += len(piece)
            card_end = start + duration * done / total
            cards.append((card_start, card_end, _two_lines(piece, line_chars)))
    return cards
