"""Soft start/stop chimes for the optional "play a sound when recording
starts/stops" setting.

Synthesized in memory (no audio asset to ship). Meant to be calm and quiet,
like a soft singing-bowl note: pure low tones, a slow gentle fade-in, a long
smooth fade-out, and the second note overlapping the first one's tail so the
two blend instead of sounding like separate beeps. A rising pair means
"recording", a falling pair means "stopped", and the stop sound is a little
quieter than the start sound.
"""

from __future__ import annotations

import io
import math
import struct
import wave

SAMPLE_RATE = 22_050

# (frequency Hz, start offset seconds, length seconds)
_START_NOTES = ((440.00, 0.00, 0.42), (659.25, 0.11, 0.50))  # A4 then E5, rising
_STOP_NOTES = ((659.25, 0.00, 0.42), (440.00, 0.11, 0.50))  # E5 then A4, falling

_PEAK = {"start": 0.14, "stop": 0.10}  # quiet: well under a third of full scale

_cache: dict[str, bytes] = {}


def _add_note(buffer: list[float], freq: float, offset: float, seconds: float) -> None:
    start = int(SAMPLE_RATE * offset)
    count = int(SAMPLE_RATE * seconds)
    attack = max(1, int(SAMPLE_RATE * 0.03))  # slow, soft fade-in
    for i in range(count):
        t = i / SAMPLE_RATE
        tone = math.sin(2 * math.pi * freq * t) + 0.08 * math.sin(2 * math.pi * 2 * freq * t)
        fade_in = math.sin(0.5 * math.pi * min(1.0, i / attack))
        decay = math.exp(-4.5 * i / count)
        index = start + i
        while index >= len(buffer):
            buffer.append(0.0)
        buffer[index] += tone * fade_in * decay


def make_chime(kind: str) -> bytes:
    """WAV bytes for the "start" or "stop" chime."""
    if kind in _cache:
        return _cache[kind]
    notes = _START_NOTES if kind == "start" else _STOP_NOTES
    samples: list[float] = []
    for freq, offset, seconds in notes:
        _add_note(samples, freq, offset, seconds)
    top = max(abs(s) for s in samples) or 1.0
    peak = _PEAK["start" if kind == "start" else "stop"]
    pcm = b"".join(struct.pack("<h", int(32767 * peak * s / top)) for s in samples)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm)
    _cache[kind] = buffer.getvalue()
    return _cache[kind]
