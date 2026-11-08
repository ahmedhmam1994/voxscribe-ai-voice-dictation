"""How long transcribing a recording will take on this PC, in plain words.

The speed is learned from real imports (core/settings.py
record_transcribe_speed). Until there is one, a cautious first guess is used
and the text says it is a guess.
"""

from __future__ import annotations

# Seconds of work per second of audio before anything was measured: a
# cautious guess for the default model on an ordinary CPU.
FIRST_GUESS = 0.35


def describe_length(seconds: float) -> str:
    """'45 s', '12 min', '1 h 20 min'."""
    seconds = max(0, round(seconds))
    if seconds < 60:
        return f"{seconds} s"
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"{minutes} min"
    hours, rest = divmod(minutes, 60)
    return f"{hours} h {rest} min" if rest else f"{hours} h"


def transcribe_time(duration: float, speed: float | None) -> str:
    """'about 4 min' from what this PC managed before, or 'roughly 4 min (a
    first guess, it learns from your imports)' when nothing was measured."""
    if speed is None:
        return f"roughly {describe_length(duration * FIRST_GUESS)} (a first guess)"
    return f"about {describe_length(max(duration * speed, 5))}"
