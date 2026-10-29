"""Records a meeting on two tracks: your microphone ("You") and whatever the PC
is playing, such as the other people on a Zoom or Teams call ("Others").

Keeping the two apart is what makes the notes useful: who spoke is known without
any model, and the two tracks can be transcribed and merged by time afterwards
(core/meeting.py).

Each track is written to a 16 kHz mono WAV file in a temporary folder as it is
recorded, so a long meeting does not fill memory and a crash does not lose it
all. Nothing leaves the PC; the files are deleted once the notes are saved.

Capturing what the PC plays ("loopback") uses the `soundcard` package. When it is
missing, or the audio device refuses, the meeting is recorded on the microphone
alone and `loopback_error` says why.
"""

from __future__ import annotations

import queue
import threading
import time
import warnings
import wave
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from core.audio_capture import SAMPLE_RATE, chunk_level, resample_to_16k

CHUNK_SECONDS = 0.2


class _WavWriter:
    """Resamples chunks to 16 kHz and appends them to a mono 16-bit WAV file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.frames = 0
        self._file = wave.open(str(path), "wb")  # noqa: SIM115 -- closed in close()
        self._file.setnchannels(1)
        self._file.setsampwidth(2)
        self._file.setframerate(SAMPLE_RATE)

    def add(self, chunk: np.ndarray, rate: int) -> None:
        samples = resample_to_16k(np.asarray(chunk, dtype=np.float32).reshape(-1), rate)
        pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16)
        self._file.writeframes(pcm.tobytes())
        self.frames += len(pcm)

    def close(self) -> None:
        self._file.close()


class _Track:
    """One source feeding one WAV file through a small queue, so the audio
    callback never waits for the disk."""

    def __init__(self, name: str, source, path: Path) -> None:  # noqa: ANN001
        self.name = name
        self.source = source
        self.writer = _WavWriter(path)
        self.level = 0.0
        self._queue: queue.Queue[np.ndarray | None] = queue.Queue()
        self._thread = threading.Thread(target=self._write_loop, daemon=True)

    def _push(self, chunk: np.ndarray) -> None:
        self._queue.put(chunk)
        level = chunk_level(np.asarray(chunk, dtype=np.float32).reshape(-1))
        self.level = max(level, self.level * 0.7)

    def _write_loop(self) -> None:
        while True:
            chunk = self._queue.get()
            if chunk is None:
                return
            self.writer.add(chunk, self.source.rate)

    def start(self) -> None:
        self._thread.start()
        try:
            self.source.start(self._push)
        except Exception:
            self._queue.put(None)
            self._thread.join()
            self.writer.close()
            raise

    def stop(self) -> None:
        try:
            self.source.stop()
        finally:
            self._queue.put(None)
            self._thread.join()
            self.writer.close()


class SoundDeviceMic:
    """The microphone, through sounddevice (the same library dictation uses)."""

    def __init__(self, device: int | None) -> None:
        from core.audio_capture import device_native_samplerate, resolve_input_device

        self._device = resolve_input_device(device)
        self.rate = device_native_samplerate(self._device)
        self._stream = None

    def start(self, push: Callable[[np.ndarray], None]) -> None:
        import sounddevice as sd

        def callback(indata, frames, time_info, status):  # noqa: ANN001
            push(indata[:, 0].copy())

        self._stream = sd.InputStream(
            samplerate=self.rate, channels=1, dtype="float32", device=self._device,
            callback=callback,
        )
        self._stream.start()

    def stop(self) -> None:
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:  # noqa: BLE001
                pass


class SoundcardLoopback:
    """Whatever the default speakers are playing, through the `soundcard` package."""

    rate = 48_000

    def __init__(self) -> None:
        import soundcard

        speaker = soundcard.default_speaker()
        self.name = str(speaker.name)
        self._mic = soundcard.get_microphone(id=self.name, include_loopback=True)
        self._running = threading.Event()
        self._thread: threading.Thread | None = None
        self._error: Exception | None = None

    def start(self, push: Callable[[np.ndarray], None]) -> None:
        self._running.set()
        ready = threading.Event()

        def run() -> None:
            try:
                warnings.filterwarnings("ignore", message="data discontinuity")
                with self._mic.recorder(samplerate=self.rate, channels=1) as recorder:
                    ready.set()
                    frames = int(self.rate * CHUNK_SECONDS)
                    while self._running.is_set():
                        push(recorder.record(numframes=frames)[:, 0])
            except Exception as exc:  # noqa: BLE001
                self._error = exc
            finally:
                ready.set()

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()
        ready.wait(timeout=5)
        if self._error is not None:
            raise self._error

    def stop(self) -> None:
        self._running.clear()
        if self._thread is not None:
            self._thread.join(timeout=3)


def loopback_available() -> bool:
    """True when this PC can capture what it is playing."""
    try:
        import soundcard

        soundcard.default_speaker()
        return True
    except Exception:  # noqa: BLE001
        return False


@dataclass
class MeetingAudio:
    mic_path: Path
    others_path: Path | None
    seconds: float
    loopback_error: str | None = None


class MeetingRecorder:
    """Starts and stops a meeting recording. `mic` and `loopback` are sources with
    `rate`, `start(push)` and `stop()`; the defaults are the real devices, and tests
    pass fakes. `loopback` may be None (microphone only)."""

    def __init__(self, folder: Path, mic=None, loopback=None, loopback_error=None):  # noqa: ANN001, ANN204
        self.folder = folder
        self._mic = mic
        self._loopback = loopback
        self.loopback_error: str | None = loopback_error
        self._tracks: list[_Track] = []
        self._started_at = 0.0
        self._stopped_at = 0.0
        self.running = False

    @property
    def mic_level(self) -> float:
        return self._tracks[0].level if self._tracks else 0.0

    @property
    def others_level(self) -> float:
        return self._tracks[1].level if len(self._tracks) > 1 else 0.0

    @property
    def has_loopback(self) -> bool:
        return len(self._tracks) > 1

    @property
    def elapsed(self) -> float:
        if not self.running:
            return self._stopped_at - self._started_at
        return time.monotonic() - self._started_at

    def start(self) -> None:
        """Raises when the microphone cannot be opened."""
        self.folder.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        mic = self._mic if self._mic is not None else SoundDeviceMic(None)
        mic_track = _Track("you", mic, self.folder / f"{stamp}-you.wav")
        mic_track.start()
        self._tracks = [mic_track]
        loopback = self._loopback
        if loopback is None and self.loopback_error is None:
            try:
                loopback = SoundcardLoopback()
            except Exception as exc:  # noqa: BLE001
                self.loopback_error = f"{type(exc).__name__}: {exc}"
        if loopback is not None:
            others = _Track("others", loopback, self.folder / f"{stamp}-others.wav")
            try:
                others.start()
                self._tracks.append(others)
            except Exception as exc:  # noqa: BLE001
                self.loopback_error = f"{type(exc).__name__}: {exc}"
                others.writer.path.unlink(missing_ok=True)
        self._started_at = time.monotonic()
        self.running = True

    def stop(self) -> MeetingAudio:
        self._stopped_at = time.monotonic()
        self.running = False
        for track in self._tracks:
            track.stop()
        mic_track = self._tracks[0]
        others_track = self._tracks[1] if len(self._tracks) > 1 else None
        return MeetingAudio(
            mic_path=mic_track.writer.path,
            others_path=others_track.writer.path if others_track else None,
            seconds=max(
                mic_track.writer.frames, others_track.writer.frames if others_track else 0
            )
            / SAMPLE_RATE,
            loopback_error=self.loopback_error,
        )


def delete_audio(audio: MeetingAudio) -> None:
    """Removes the temporary recordings once the notes are saved."""
    for path in (audio.mic_path, audio.others_path):
        if path is not None:
            path.unlink(missing_ok=True)


def clean_stale(folder: Path, older_than_seconds: float = 24 * 3600) -> int:
    """Deletes leftover recordings from a meeting that was never finished (a crash
    or a closed PC), so audio does not pile up on disk. Returns how many went."""
    removed = 0
    if not folder.is_dir():
        return 0
    now = time.time()
    for path in folder.glob("*.wav"):
        try:
            if now - path.stat().st_mtime > older_than_seconds:
                path.unlink()
                removed += 1
        except OSError:
            continue
    return removed
