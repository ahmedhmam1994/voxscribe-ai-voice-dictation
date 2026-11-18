"""Tests for core/transcribe.py's loose_vad_threshold: which silence-filter
threshold a recording is decoded with.

It must stay at the default for anything that is not band-limited speech, so
that noise never gets handed to Whisper as speech. Speech is stood in for by a
fake detector, since the real Silero model is covered by the benchmark, not here.
"""

import numpy as np
import pytest

from core import transcribe
from core.transcribe import (
    LOOSE_VAD_THRESHOLD,
    STRICT_VAD_THRESHOLD,
    loose_vad_threshold,
)

RATE = 16_000


def _detector(monkeypatch: pytest.MonkeyPatch, strict_seconds: float, loose_seconds: float) -> None:
    """Makes the speech finder report this much speech at each threshold."""
    import faster_whisper.vad as vad

    def fake(audio, vad_options=None, sampling_rate=RATE, **kwargs):  # noqa: ANN001, ANN003, ANN202
        seconds = loose_seconds if vad_options.threshold < 0.5 else strict_seconds
        return [{"start": 0, "end": int(seconds * RATE)}] if seconds else []

    monkeypatch.setattr(vad, "get_speech_timestamps", fake)


def _clip(seconds: float) -> np.ndarray:
    return np.zeros(int(seconds * RATE), dtype=np.float32)


def test_normal_speech_keeps_the_default(monkeypatch):
    _detector(monkeypatch, strict_seconds=3.5, loose_seconds=3.6)
    assert loose_vad_threshold(_clip(4)) == STRICT_VAD_THRESHOLD


def test_band_limited_speech_gets_the_loose_threshold(monkeypatch):
    # The strict filter keeps 0.7 s of a 4.8 s clip; the loose one keeps all of it.
    _detector(monkeypatch, strict_seconds=0.7, loose_seconds=4.8)
    assert loose_vad_threshold(_clip(4.8)) == LOOSE_VAD_THRESHOLD


def test_speech_with_nothing_found_by_the_strict_filter_gets_the_loose_threshold(monkeypatch):
    _detector(monkeypatch, strict_seconds=0, loose_seconds=4.0)
    assert loose_vad_threshold(_clip(4.1)) == LOOSE_VAD_THRESHOLD


def test_a_burst_of_noise_keeps_the_default(monkeypatch):
    # Room noise the loose filter mistakes for speech for 0.8 s of a 4 s clip.
    _detector(monkeypatch, strict_seconds=0, loose_seconds=0.8)
    assert loose_vad_threshold(_clip(4)) == STRICT_VAD_THRESHOLD


def test_a_small_gain_keeps_the_default(monkeypatch):
    _detector(monkeypatch, strict_seconds=3.0, loose_seconds=3.3)
    assert loose_vad_threshold(_clip(4)) == STRICT_VAD_THRESHOLD


def test_a_failing_detector_never_stops_a_dictation(monkeypatch):
    import faster_whisper.vad as vad

    def boom(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise RuntimeError("model missing")

    monkeypatch.setattr(vad, "get_speech_timestamps", boom)
    assert loose_vad_threshold(_clip(4)) == STRICT_VAD_THRESHOLD


def test_thresholds_are_ordered():
    assert transcribe.LOOSE_VAD_THRESHOLD < transcribe.STRICT_VAD_THRESHOLD
