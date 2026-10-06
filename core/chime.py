"""Soft start/stop chimes for the optional "play a sound when recording
starts/stops" setting.

Synthesized in memory (no audio asset to ship): a short two-note chime made
of a sine tone with a touch of second harmonic and a quick, smooth fade, so it
sounds like a gentle jingle rather than a system beep. Rising notes mean
"recording", falling notes mean "stopped".
"""

from __future__ import annotations

import io
import math
import struct
import wave

SAMPLE_RATE = 22_050
_PEAK = 0.30  # well below full scale: gentle, never clipping

# (frequency Hz, note length seconds)
_START_NOTES = ((659.25, 0.09), (987.77, 0.14))  # E5 then B5, rising
_STOP_NOTES = ((987.77, 0.09), (659.25, 0.14))  # B5 then E5, falling

_cache: dict[str, bytes] = {}


def _note(freq: float, seconds: float) -> list[float]:
    count = int(SAMPLE_RATE * seconds)
    attack = max(1, int(SAMPLE_RATE * 0.008))
    samples = []
    for i in range(count):
        t = i / SAMPLE_RATE
        tone = math.sin(2 * math.pi * freq * t) + 0.25 * math.sin(2 * math.pi * 2 * freq * t)
        fade_in = min(1.0, i / attack)
        decay = math.exp(-5.0 * i / count)
        samples.append(tone * fade_in * decay)
    return samples


def make_chime(kind: str) -> bytes:
    """WAV bytes for the "start" or "stop" chime."""
    if kind in _cache:
        return _cache[kind]
    notes = _START_NOTES if kind == "start" else _STOP_NOTES
    samples: list[float] = []
    for freq, seconds in notes:
        samples.extend(_note(freq, seconds))
    top = max(abs(s) for s in samples) or 1.0
    pcm = b"".join(struct.pack("<h", int(32767 * _PEAK * s / top)) for s in samples)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm)
    _cache[kind] = buffer.getvalue()
    return _cache[kind]
