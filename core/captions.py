"""Splits long transcript segments into caption cards that fit on screen.

Whisper returns whole segments, some of them long. Captions read best at
about 42 characters a line and two lines a card (the common broadcast and
YouTube guidance), so a long segment is cut into several cards. Times are
shared out by text length, since only segment level times are available.
Pure string logic with no Whisper dependency, like core/srt.py.
"""

from __future__ import annotations

Segment = tuple[float, float, str]
Word = tuple[float, float, str]
DetailedSegment = tuple[float, float, str, list[Word]]

DEFAULT_LINE_CHARS = 42
MAX_LINES = 2


def _balanced_chunks(text: str, limit: int, gaps: list[float] | None = None) -> list[str]:
    """Cuts text into the fewest cards of at most `limit` characters, with the
    pieces about equal in length (no one word tail card that flashes by).
    Cuts prefer a pause in the speech, then the end of a sentence, then a clause,
    then any space. `gaps[k]` is the silence after word k, when known."""
    text = text.strip()
    if len(text) <= limit:
        return [text]
    start_count = -(-len(text) // limit)
    for count in range(start_count, start_count + 4):
        pieces = _cut_into(text, limit, count, gaps)
        if pieces is not None:
            return pieces
    return [text]


def _cut_into(text: str, limit: int, count: int, gaps: list[float] | None) -> list[str] | None:
    """Exactly `count` pieces of at most `limit` characters, or None if no cut works."""
    pieces: list[str] = []
    rest = text
    consumed = 0
    for left in range(count, 1, -1):
        target = len(rest) / left
        lowest = max(1, len(rest) - limit * (left - 1))
        best = None
        for i, ch in enumerate(rest[: limit + 1]):
            if ch != " " or i < lowest:
                continue
            before = rest[:i].rstrip()
            if before.endswith((".", "?", "!")):
                bonus = 12.0
            elif before.endswith((";", ":", ",")):
                bonus = 6.0
            else:
                bonus = 0.0
            if gaps:
                k = consumed + len(rest[:i].split()) - 1
                if 0 <= k < len(gaps):
                    bonus += min(gaps[k], 2.0) * 10
            score = abs(i - target) - bonus
            if best is None or score < best[0]:
                best = (score, i)
        if best is None:
            return None
        pieces.append(rest[: best[1]].strip())
        consumed += len(pieces[-1].split())
        rest = rest[best[1] :].strip()
    if len(rest) > limit:
        return None
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


HOLD_SECONDS = 0.3


def _tidy_timing(cards: list[Segment]) -> list[Segment]:
    """Gives each card a readable on screen time without crossing the next one:
    it lingers a moment after the last word, lasts at least MIN_CARD_SECONDS
    when there is room, and never starts before the previous card ended."""
    out: list[Segment] = []
    for i, (start, end, text) in enumerate(cards):
        if out and start < out[-1][1]:
            start = out[-1][1]
        next_start = cards[i + 1][0] if i + 1 < len(cards) else None
        end = max(end, start)
        end += HOLD_SECONDS
        if end - start < MIN_CARD_SECONDS:
            end = start + MIN_CARD_SECONDS
        if next_start is not None and end > next_start:
            end = max(next_start, start)
        out.append((start, end, text))
    return out


PAUSE_SPLIT_SECONDS = 1.5


def _split_at_pauses(words: list[Word]) -> list[list[Word]]:
    """Groups of words with no long silence inside, so one card never spans a pause."""
    groups: list[list[Word]] = [[words[0]]]
    for previous, word in zip(words, words[1:], strict=False):
        if word[0] - previous[1] > PAUSE_SPLIT_SECONDS:
            groups.append([])
        groups[-1].append(word)
    return groups


def split_segments_timed(
    segments: list[DetailedSegment], line_chars: int = DEFAULT_LINE_CHARS
) -> list[Segment]:
    """Like split_segments, but each card is timed from the words it holds, so
    it appears when its first word is spoken and leaves soon after its last.
    A segment whose words do not match its text (for example one with a speaker
    label added) falls back to the even split by text length."""
    if line_chars <= 0:
        return [(start, end, text) for start, end, text, _words in segments]
    cards: list[Segment] = []
    for start, end, text, words in segments:
        text = " ".join(text.split())
        if not text:
            continue
        words = [(w_start, w_end, w_text.strip()) for w_start, w_end, w_text in words]
        if not words or " ".join(w[2] for w in words).split() != text.split():
            cards.extend(split_segments([(start, end, text)], line_chars))
            continue
        for group in _split_at_pauses(words):
            group_text = " ".join(w[2] for w in group)
            gaps = [group[k + 1][0] - group[k][1] for k in range(len(group) - 1)]
            used = 0
            for piece in _balanced_chunks(group_text, line_chars * MAX_LINES, gaps):
                count = len(piece.split())
                chunk = group[used : used + count]
                used += count
                cards.append((chunk[0][0], chunk[-1][1], _two_lines(piece, line_chars)))
    return _tidy_timing(cards)


MAX_CHARS_PER_SECOND = 21.0
MIN_CARD_SECONDS = 1.0
LONG_GAP_SECONDS = 3.0
MAX_CARD_SECONDS = 7.0


def review_flags(cards: list[Segment]) -> list[tuple[int, str]]:
    """Cards worth a second look, as (card number, reason). Flags only: it
    never changes a word or a time. Cards are numbered from 1, as in the .srt.

    A card is flagged when it is on screen too briefly to read or far too long,
    when it starts
    before the previous one ended, or when the silence before it is unusually
    long (a possible missed stretch of speech).
    """
    flags: list[tuple[int, str]] = []
    previous_end = None
    for number, (start, end, text) in enumerate(cards, start=1):
        duration = end - start
        chars = len(" ".join(text.split()))
        if duration > MAX_CARD_SECONDS:
            flags.append((number, f"on screen for {duration:.0f}s, longer than the speech needs"))
        elif duration < MIN_CARD_SECONDS:
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
