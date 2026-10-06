"""Tests for the soft start/stop chimes in core/chime.py."""

import io
import wave

import numpy as np

from core import chime


def _load(kind):
    with wave.open(io.BytesIO(chime.make_chime(kind))) as wav:
        frames = wav.readframes(wav.getnframes())
        return wav, np.frombuffer(frames, dtype="<i2"), wav.getframerate()


def test_chimes_are_short_valid_mono_wavs():
    for kind in ("start", "stop"):
        with wave.open(io.BytesIO(chime.make_chime(kind))) as wav:
            assert wav.getnchannels() == 1
            assert wav.getsampwidth() == 2
            assert wav.getframerate() == chime.SAMPLE_RATE
            assert 0.15 < wav.getnframes() / wav.getframerate() < 0.4


def test_chimes_are_gentle_and_not_clipped():
    for kind in ("start", "stop"):
        _wav, samples, _rate = _load(kind)
        peak = np.max(np.abs(samples)) / 32767
        assert 0.2 < peak < 0.4


def test_start_and_stop_differ_and_are_cached():
    assert chime.make_chime("start") != chime.make_chime("stop")
    assert chime.make_chime("start") is chime.make_chime("start")
