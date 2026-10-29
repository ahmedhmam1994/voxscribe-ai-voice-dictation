import os
import time
import wave

import numpy as np
import pytest

from core import meeting_recorder
from core.meeting_recorder import MeetingRecorder


class FakeSource:
    """Pushes a steady tone in 0.1 s chunks from a thread, like a device would."""

    def __init__(self, rate=48_000, amplitude=0.3, fail_on_start=False):
        self.rate = rate
        self.amplitude = amplitude
        self.fail_on_start = fail_on_start
        self.started = False
        self.stopped = False
        self._push = None

    def start(self, push):
        if self.fail_on_start:
            raise RuntimeError("device refused")
        self.started = True
        t = np.arange(int(self.rate * 0.1)) / self.rate
        chunk = (self.amplitude * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        for _ in range(5):  # half a second of audio
            push(chunk)

    def stop(self):
        self.stopped = True


def _read(path):
    with wave.open(str(path)) as w:
        return w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()


def test_two_tracks_are_written_as_16k_mono_wav(tmp_path):
    recorder = MeetingRecorder(tmp_path, FakeSource(), FakeSource(rate=44_100))
    recorder.start()
    audio = recorder.stop()
    assert recorder.has_loopback
    for path in (audio.mic_path, audio.others_path):
        rate, channels, width, frames = _read(path)
        assert (rate, channels, width) == (16_000, 1, 2)
        assert frames == pytest.approx(8000, abs=40)  # 0.5 s at 16 kHz
    assert audio.seconds == pytest.approx(0.5, abs=0.01)
    assert audio.loopback_error is None


def test_microphone_only_when_there_is_no_loopback(tmp_path):
    recorder = MeetingRecorder(tmp_path, FakeSource(), None, loopback_error="not installed")
    recorder.start()
    audio = recorder.stop()
    assert audio.others_path is None
    assert audio.loopback_error == "not installed"
    assert not recorder.has_loopback


def test_a_loopback_that_fails_to_start_leaves_the_microphone_recording(tmp_path):
    recorder = MeetingRecorder(tmp_path, FakeSource(), FakeSource(fail_on_start=True))
    recorder.start()
    audio = recorder.stop()
    assert audio.others_path is None
    assert "device refused" in audio.loopback_error
    assert audio.mic_path.exists()
    assert not list(tmp_path.glob("*-others.wav"))


def test_a_microphone_that_fails_stops_the_meeting_from_starting(tmp_path):
    recorder = MeetingRecorder(tmp_path, FakeSource(fail_on_start=True), FakeSource())
    with pytest.raises(RuntimeError):
        recorder.start()
    assert not recorder.running


def test_levels_follow_the_audio_and_elapsed_time_stops_counting(tmp_path):
    recorder = MeetingRecorder(tmp_path, FakeSource(amplitude=0.3), FakeSource(amplitude=0.0))
    recorder.start()
    assert recorder.running
    time.sleep(0.05)
    assert recorder.mic_level > recorder.others_level
    recorder.stop()
    first = recorder.elapsed
    time.sleep(0.05)
    assert recorder.elapsed == first


def test_delete_audio_removes_both_files(tmp_path):
    recorder = MeetingRecorder(tmp_path, FakeSource(), FakeSource())
    recorder.start()
    audio = recorder.stop()
    meeting_recorder.delete_audio(audio)
    assert not list(tmp_path.glob("*.wav"))


def test_stale_recordings_are_cleaned_but_recent_ones_stay(tmp_path):
    old, new = tmp_path / "old.wav", tmp_path / "new.wav"
    for path in (old, new):
        path.write_bytes(b"x")
    long_ago = time.time() - 3 * 24 * 3600
    os.utime(old, (long_ago, long_ago))
    assert meeting_recorder.clean_stale(tmp_path) == 1
    assert not old.exists() and new.exists()
    assert meeting_recorder.clean_stale(tmp_path / "missing") == 0
