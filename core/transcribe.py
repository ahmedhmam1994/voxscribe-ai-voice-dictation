"""Speech-to-text transcription and segmenting.

Two pieces live here:

- `Transcriber`: thin wrapper around `faster-whisper`. Feed it a buffer of
  float32 audio at 16kHz, get text back.
- `SegmentingTranscriber`: consumes frames from `core.audio_capture`, runs
  them through a `SileroVAD` instance, buffers audio while speech is
  detected, and once a long-enough silence hangover has elapsed, sends the
  buffered segment to `Transcriber` and yields the resulting text. This is
  what turns "raw mic + VAD" into "sentences of text".
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

from core.vad import SAMPLE_RATE, SileroVAD

# "small" trades some CPU speed for meaningfully better accuracy than
# "base" -- worth it given this user's mic (compressed Bluetooth headset
# audio) already makes transcription harder than a typical clean mic.
# int8 compute type keeps CPU inference reasonably fast despite the larger
# model.
DEFAULT_MODEL_SIZE = "small"

# How long a continuous run of silence must be (in seconds) after speech
# before we consider the segment finished and send it to Whisper. Longer
# than the ~96ms used in the Phase 2 VAD test so natural mid-sentence
# pauses/breaths don't prematurely cut a segment.
DEFAULT_HANGOVER_SEC = 1.2

# Segments shorter than this (in seconds) are dropped as noise blips
# instead of being sent to Whisper.
DEFAULT_MIN_SEGMENT_SEC = 0.25

# Require this many consecutive speech-classified frames before actually
# starting a segment. Without this, a single noisy frame (background sound,
# a mic bump) can trigger a segment that gets sent to Whisper -- and Whisper
# doesn't just fail quietly on non-speech audio, it "hallucinates" plausible
# -sounding fake sentences from noise. This debounce (~130ms) filters out
# single-frame spikes while still catching real speech almost instantly.
DEFAULT_START_DEBOUNCE_FRAMES = 4

_FRAME_SIZE = 512  # samples per VAD frame (see core/vad.py)
_FRAME_DURATION_SEC = _FRAME_SIZE / SAMPLE_RATE  # 32ms

# Recordings whose loudest sample is below this (about -54 dBFS) are treated
# as silence instead of being normalized up and sent to Whisper.
SILENCE_PEAK_FLOOR = 0.002

# Approximate download size of each model, in MB, only used to show progress
# while a first-run download is in flight.
MODEL_APPROX_MB = {
    "tiny": 75,
    "base": 145,
    "small": 484,
    "medium": 1530,
    "large": 3090,
    "large-v3": 3090,
}


def _hf_cache_root() -> Path:
    env = os.environ.get("HF_HUB_CACHE")
    if env:
        return Path(env)
    home = os.environ.get("HF_HOME")
    if home:
        return Path(home) / "hub"
    return Path.home() / ".cache" / "huggingface" / "hub"


def model_cache_dir(model_size: str) -> Path:
    """Where faster-whisper stores `model_size` after downloading it."""
    repo = "faster-whisper-large-v3" if model_size == "large" else f"faster-whisper-{model_size}"
    return _hf_cache_root() / f"models--Systran--{repo}"


def model_cache_bytes(model_size: str) -> int:
    """Bytes currently on disk for this model, including a partial download."""
    root = model_cache_dir(model_size)
    total = 0
    try:
        for path in root.rglob("*"):
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
    except OSError:
        pass
    return total


def purge_model_cache(model_size: str) -> bool:
    """Delete a model's cache folder so the next load downloads it fresh.
    Used when a cached copy is broken (interrupted download, a file removed
    by antivirus). Returns whether anything was removed."""
    root = model_cache_dir(model_size)
    if not root.exists():
        return False
    shutil.rmtree(root, ignore_errors=True)
    return not root.exists()


# How long to wait between attempts when a cached model file exists but can't
# be opened yet. A freshly downloaded 480 MB model is often locked by
# antivirus while it is being scanned, which can take a while.
_LOCKED_FILE_RETRY_DELAYS_SEC = (3, 6, 12)


def _model_bin_present(model_size: str) -> bool:
    """Whether the cached model has a non-trivial model.bin file."""
    try:
        for path in model_cache_dir(model_size).glob("snapshots/*/model.bin"):
            if path.stat().st_size > 1_000_000:
                return True
    except OSError:
        pass
    return False


def load_transcriber(model_size: str) -> "Transcriber":
    """Load a Transcriber, repairing a broken cached model once.

    If the first load fails because the cached model file can't be opened:
    when the file is there, wait and retry a few times first (a just-finished
    download is commonly locked by antivirus scanning, and deleting it would
    only force a pointless re-download). If it still fails, or the file is
    missing or empty, delete the cached copy and download it again once. A
    second failure is raised to the caller (no network, disk full, ...).
    """
    try:
        return Transcriber(model_size=model_size)
    except Exception as exc:  # noqa: BLE001
        if not looks_like_broken_cache(exc):
            raise
        first_error = exc

    if _model_bin_present(model_size):
        for delay in _LOCKED_FILE_RETRY_DELAYS_SEC:
            time.sleep(delay)
            try:
                return Transcriber(model_size=model_size)
            except Exception as retry_exc:  # noqa: BLE001
                if not looks_like_broken_cache(retry_exc):
                    raise

    if not purge_model_cache(model_size):
        raise first_error
    return Transcriber(model_size=model_size)


def looks_like_broken_cache(exc: Exception) -> bool:
    """True for load errors caused by an unreadable cached model file, as
    opposed to e.g. being offline during a first download (where deleting
    a partial download would only throw away progress)."""
    text = str(exc).lower()
    return any(
        marker in text
        for marker in ("model.bin", "unable to open file", "corrupt")
    )


class Transcriber:
    """Wraps a `faster-whisper` model for one-shot buffer transcription."""

    def __init__(
        self,
        model_size: str = DEFAULT_MODEL_SIZE,
        device: str = "cpu",
        compute_type: str = "int8",
    ):
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe(
        self,
        audio: np.ndarray,
        language: str | None = "en",
        initial_prompt: str | None = None,
        task: str = "transcribe",
    ) -> str:
        """Transcribe a float32 mono buffer at 16kHz, return the text.

        `language`: an ISO 639-1 code (e.g. "en", "es", "ar") to force a
        specific spoken language, or None to let Whisper auto-detect which
        language is being spoken. Defaults to "en" so any caller that
        doesn't pass one explicitly keeps this class's original behavior.
        `DEFAULT_MODEL_SIZE` ("small", not "small.en") is already the
        multilingual model -- this was always just an unexposed capability,
        not something that needs a different/bigger model downloaded.

        `initial_prompt`: optional prior-context text (see
        core/settings.py's custom_vocabulary_prompt()) that biases the
        decoder toward specific words/names it's given without instructing
        it to transcribe that text itself -- the local equivalent of Wispr
        Flow's custom dictionary.

        `task`: "transcribe" (default) writes out what was said, in the
        language it was spoken in. "translate" is Whisper's own built-in
        X-to-English task -- it always translates into English specifically
        (not an arbitrary target language), regardless of `language`, which
        here just tells it what's being spoken, not what to output. No
        separate model or extra work needed, this capability already ships
        inside the same Whisper model VoxScribe already downloads.

        Returns an empty string if no speech is recognized.
        """
        # Normalize to a healthy peak level before transcribing. Unlike the
        # VAD's fixed digital gain (which risks clipping/distortion in a
        # real-time per-frame context), this is a one-shot peak-normalize on
        # the whole finished segment, so it safely boosts quiet mics (like
        # this user's Bluetooth headset) without introducing artifacts.
        if len(audio) == 0:
            return ""
        peak = np.max(np.abs(audio))
        if peak < SILENCE_PEAK_FLOOR:
            # Effectively silence (muted or disconnected mic, a tap on the
            # hotkey). Boosting this to a healthy level would hand Whisper
            # loud noise, and Whisper answers noise with invented sentences.
            return ""
        if peak < 0.5:
            audio = audio * (0.5 / peak)

        segments, _info = self.model.transcribe(
            audio,
            language=language,
            initial_prompt=initial_prompt,
            task=task,
            # Let faster-whisper's own bundled VAD trim leading/trailing
            # silence within the clip -- useful now that recording is
            # manually started/stopped (push-to-talk) rather than gated by
            # our own real-time VAD.
            vad_filter=True,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()

    def transcribe_file(
        self,
        path: str,
        language: str | None = "en",
        initial_prompt: str | None = None,
        task: str = "transcribe",
    ) -> str:
        """Transcribe an existing audio/video file on disk, return the text.

        Unlike `transcribe()`, this hands the file path straight to
        faster-whisper rather than a decoded numpy buffer: it decodes the
        file itself via the bundled `av` (PyAV/ffmpeg) dependency, so any
        container/codec ffmpeg understands works (mp3, m4a, mp4, mov, flac,
        ...), not just raw PCM. No peak-normalization pass here -- that's
        specifically a fix for this app's own quiet live-mic capture, not
        something to assume about an arbitrary file someone drops in.

        `task`: see `transcribe()` -- "translate" outputs English regardless
        of the spoken language.
        """
        segments = self.transcribe_file_segments(
            path, language=language, initial_prompt=initial_prompt, task=task
        )
        return " ".join(text.strip() for _start, _end, text in segments).strip()

    def transcribe_file_segments(
        self,
        path: str,
        language: str | None = "en",
        initial_prompt: str | None = None,
        task: str = "transcribe",
    ) -> list[tuple[float, float, str]]:
        """Like `transcribe_file()`, but keeps each segment's start/end time
        (in seconds) instead of flattening to one string -- what SRT caption
        export needs that plain transcription doesn't.
        """
        segments, _info = self.model.transcribe(
            path,
            language=language,
            initial_prompt=initial_prompt,
            task=task,
            vad_filter=True,
        )
        return [(seg.start, seg.end, seg.text.strip()) for seg in segments]


class SegmentingTranscriber:
    """Turns a stream of VAD frames into transcribed text segments.

    Usage:
        st = SegmentingTranscriber()
        for frame in frames():
            for event in st.push(frame):
                # event is a dict like {"type": "speech_start"} or
                # {"type": "speech_end"} or {"type": "text", "text": "..."}
                ...

    Call `push()` once per audio frame (512 samples / 32ms at 16kHz, as
    produced by `core.audio_capture.frames()`). It returns a list of zero
    or more events produced by that frame, usually empty, occasionally
    a status change or a finished transcription.
    """

    def __init__(
        self,
        vad: SileroVAD | None = None,
        transcriber: Transcriber | None = None,
        hangover_sec: float = DEFAULT_HANGOVER_SEC,
        min_segment_sec: float = DEFAULT_MIN_SEGMENT_SEC,
        start_debounce_frames: int = DEFAULT_START_DEBOUNCE_FRAMES,
    ):
        self.vad = vad or SileroVAD()
        self.transcriber = transcriber or Transcriber()
        self.hangover_frames = max(1, round(hangover_sec / _FRAME_DURATION_SEC))
        self.min_segment_frames = max(1, round(min_segment_sec / _FRAME_DURATION_SEC))
        self.start_debounce_frames = start_debounce_frames

        self._in_speech = False
        self._silence_run = 0
        self._buffer: list[np.ndarray] = []
        # Frames provisionally classified as speech but not yet confirmed
        # past the start debounce -- held here so they aren't lost if the
        # run turns out to be real speech (not discarded as noise).
        self._pending: list[np.ndarray] = []
        self._pending_run = 0

    def push(self, frame: np.ndarray) -> list[dict]:
        """Feed one audio frame in. Returns a list of events (see class docstring)."""
        events: list[dict] = []
        is_speech = self.vad.is_speech(frame)

        if self._in_speech:
            if is_speech:
                self._silence_run = 0
                self._buffer.append(frame)
            else:
                # Still inside a speech segment, but this frame is silence.
                # Keep buffering through the hangover window so we don't
                # chop off trailing audio right at the cutoff.
                self._buffer.append(frame)
                self._silence_run += 1
                if self._silence_run >= self.hangover_frames:
                    events.append({"type": "speech_end"})
                    events.extend(self._finish_segment())
            return events

        # Not currently in a confirmed speech segment -- debounce before
        # starting one, so a single noisy frame can't trigger a segment.
        if is_speech:
            self._pending.append(frame)
            self._pending_run += 1
            if self._pending_run >= self.start_debounce_frames:
                self._in_speech = True
                self._buffer = self._pending
                self._pending = []
                self._pending_run = 0
                self._silence_run = 0
                events.append({"type": "speech_start"})
        else:
            self._pending = []
            self._pending_run = 0

        return events

    def flush(self) -> list[dict]:
        """Force-finish any in-progress segment (e.g. on shutdown)."""
        if not self._in_speech:
            return []
        events = [{"type": "speech_end"}]
        events.extend(self._finish_segment())
        return events

    def _finish_segment(self) -> list[dict]:
        buffer = self._buffer
        self._buffer = []
        self._in_speech = False
        self._silence_run = 0

        if len(buffer) < self.min_segment_frames:
            return []  # too short, likely a noise blip, drop it

        audio = np.concatenate(buffer).astype(np.float32)
        text = self.transcriber.transcribe(audio)
        if not text:
            return []
        return [{"type": "text", "text": text}]
