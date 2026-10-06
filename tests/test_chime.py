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
            assert 0.3 < wav.getnframes() / wav.getframerate() < 0.8


def test_chimes_are_gentle_and_not_clipped():
    for kind in ("start", "stop"):
        _wav, samples, _rate = _load(kind)
        peak = np.max(np.abs(samples)) / 32767
        assert 0.05 < peak < 0.2


def test_start_and_stop_differ_and_are_cached():
    assert chime.make_chime("start") != chime.make_chime("stop")
    assert chime.make_chime("start") is chime.make_chime("start")


def test_stop_is_quieter_than_start():
    _w, start, _r = _load("start")
    _w, stop, _r = _load("stop")
    assert np.max(np.abs(stop)) < np.max(np.abs(start))


def test_fades_in_softly_and_out_to_silence():
    _w, samples, rate = _load("start")
    first_ms = np.abs(samples[: int(rate * 0.002)]).max() / 32767
    last_ms = np.abs(samples[-int(rate * 0.02):]).max() / 32767
    assert samples[0] == 0 and first_ms < 0.03   # starts from silence, no click
    assert last_ms < 0.01    # ends in near silence, no cut-off
