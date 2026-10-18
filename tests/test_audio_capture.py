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


def test_rolling_buffer_keeps_only_recent_audio():
    from core.audio_capture import RollingBuffer

    buf = RollingBuffer(max_samples=100)
    for i in range(10):
        buf.push(np.full(30, i, dtype=np.float32))
    kept = np.concatenate(buf.drain())
    assert len(kept) >= 100
    assert len(kept) < 100 + 30
    assert kept[-1] == 9


def test_chunk_level_silence_and_empty_are_zero():
    from core.audio_capture import chunk_level

    assert chunk_level(np.zeros(480, dtype=np.float32)) == 0.0
    assert chunk_level(np.zeros(0, dtype=np.float32)) == 0.0


def test_chunk_level_quiet_mic_still_registers():
    from core.audio_capture import chunk_level

    # A quiet Bluetooth headset: speech peaking around 0.02 must still move
    # the meter clearly, not sit at the bottom.
    t = np.linspace(0, 0.03, 480, endpoint=False)
    quiet = (0.02 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    assert 0.3 < chunk_level(quiet) < 0.9


def test_chunk_level_loud_is_capped_at_one():
    from core.audio_capture import chunk_level

    assert chunk_level(np.ones(480, dtype=np.float32)) == 1.0


def test_chunk_level_rises_with_volume():
    from core.audio_capture import chunk_level

    t = np.linspace(0, 0.03, 480, endpoint=False)
    tone = np.sin(2 * np.pi * 220 * t).astype(np.float32)
    assert chunk_level(0.005 * tone) < chunk_level(0.02 * tone) < chunk_level(0.08 * tone)


def test_rolling_buffer_drain_empties_it():
    from core.audio_capture import RollingBuffer

    buf = RollingBuffer(max_samples=50)
    buf.push(np.ones(20, dtype=np.float32))
    assert len(buf.drain()) == 1
    assert buf.drain() == []
