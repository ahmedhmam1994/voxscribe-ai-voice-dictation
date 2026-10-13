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


def _balanced_chunks(text: str, limit: int) -> list[str]:
    """Cuts text into the fewest cards of at most `limit` characters, with the
    pieces about equal in length (no one word tail card that flashes by).
    Cuts prefer the end of a sentence, then a clause, then any space."""
    text = text.strip()
    if len(text) <= limit:
        return [text]
    count = -(-len(text) // limit)
    pieces: list[str] = []
    rest = text
    for left in range(count, 1, -1):
        target = len(rest) / left
        lowest = max(1, len(rest) - limit * (left - 1))
        best = None
        for i, ch in enumerate(rest[: limit + 1]):
            if ch != " " or i < lowest:
                continue
            before = rest[:i].rstrip()
            if before.endswith((".", "?", "!")):
                bonus = 12
            elif before.endswith((";", ":", ",")):
                bonus = 6
            else:
                bonus = 0
            score = abs(i - target) - bonus
            if best is None or score < best[0]:
                best = (score, i)
        if best is None:
            break
        pieces.append(rest[: best[1]].strip())
        rest = rest[best[1] :].strip()
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
        pieces = _balanced_chunks(text, line_chars * MAX_LINES)
        total = sum(len(p) for p in pieces)
        duration = max(end - start, 0.0)
        done = 0
        for piece in pieces:
            card_start = start + duration * done / total
            done += len(piece)
            card_end = start + duration * done / total
            cards.append((card_start, card_end, _two_lines(piece, line_chars)))
    return cards


MAX_CHARS_PER_SECOND = 21.0
MIN_CARD_SECONDS = 1.0
LONG_GAP_SECONDS = 3.0


def review_flags(cards: list[Segment]) -> list[tuple[int, str]]:
    """Cards worth a second look, as (card number, reason). Flags only: it
    never changes a word or a time. Cards are numbered from 1, as in the .srt.

    A card is flagged when it is on screen too briefly to read, when it starts
    before the previous one ended, or when the silence before it is unusually
    long (a possible missed stretch of speech).
    """
    flags: list[tuple[int, str]] = []
    previous_end = None
    for number, (start, end, text) in enumerate(cards, start=1):
        duration = end - start
        chars = len(" ".join(text.split()))
        if duration < MIN_CARD_SECONDS:
            flags.append((number, f"on screen for only {duration:.1f}s"))
        elif chars / duration > MAX_CHARS_PER_SECOND:
            flags.append((number, f"too fast to read ({chars / duration:.0f} characters a second)"))
        if previous_end is not None:
            if start < previous_end - 0.001:
                flags.append((number, f"overlaps the previous card by {previous_end - start:.1f}s"))
            elif start - previous_end > LONG_GAP_SECONDS:
                flags.append((number, f"{start - previous_end:.0f}s of silence before it"))
        previous_end = end
    return flags
