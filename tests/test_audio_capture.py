"""Tests for the pure-math parts of core/audio_capture.py.

Device-querying functions (_default_input_device, device_native_samplerate)
need real/mocked sounddevice hardware and aren't covered here -- resample_to_16k
is plain numpy math and is the part most likely to silently regress.
"""

import numpy as np

from core.audio_capture import SAMPLE_RATE, resample_to_16k


def test_resample_no_op_when_already_target_rate():
    audio = np.array([0.1, 0.2, 0.3], dtype=np.float32)
    result = resample_to_16k(audio, SAMPLE_RATE)
    assert np.array_equal(result, audio)


def test_resample_empty_array():
    audio = np.zeros(0, dtype=np.float32)
    result = resample_to_16k(audio, 48_000)
    assert len(result) == 0


def test_resample_downsamples_48k_to_16k():
    # 1 second of audio at 48kHz should become ~1 second at 16kHz.
    source_rate = 48_000
    audio = np.linspace(-1.0, 1.0, num=source_rate, dtype=np.float32)
    result = resample_to_16k(audio, source_rate)
    assert abs(len(result) - SAMPLE_RATE) <= 1


def test_resample_upsamples_8k_to_16k():
    source_rate = 8_000
    audio = np.linspace(-1.0, 1.0, num=source_rate, dtype=np.float32)
    result = resample_to_16k(audio, source_rate)
    assert abs(len(result) - SAMPLE_RATE) <= 1


def test_resample_preserves_value_range():
    audio = np.linspace(-0.5, 0.5, num=48_000, dtype=np.float32)
    result = resample_to_16k(audio, 48_000)
    assert result.min() >= -0.5 - 1e-3
    assert result.max() <= 0.5 + 1e-3


def test_resample_returns_float32():
    audio = np.linspace(-1.0, 1.0, num=48_000, dtype=np.float64)
    result = resample_to_16k(audio, 48_000)
    assert result.dtype == np.float32
