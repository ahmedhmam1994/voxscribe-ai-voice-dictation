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

from collections.abc import Callable, Iterator

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


class Transcriber:
    """Wraps a `faster-whisper` model for one-shot buffer transcription."""

    def __init__(
        self,
        model_size: str = DEFAULT_MODEL_SIZE,
        device: str = "cpu",
        compute_type: str = "int8",
    ):
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe(self, audio: np.ndarray) -> str:
        """Transcribe a float32 mono buffer at 16kHz, return the text.

        Returns an empty string if no speech is recognized.
        """
        # Normalize to a healthy peak level before transcribing. Unlike the
        # VAD's fixed digital gain (which risks clipping/distortion in a
        # real-time per-frame context), this is a one-shot peak-normalize on
        # the whole finished segment, so it safely boosts quiet mics (like
        # this user's Bluetooth headset) without introducing artifacts.
        peak = np.max(np.abs(audio))
        if 0 < peak < 0.5:
            audio = audio * (0.5 / peak)

        segments, _info = self.model.transcribe(
            audio,
            language="en",
            # Let faster-whisper's own bundled VAD trim leading/trailing
            # silence within the clip -- useful now that recording is
            # manually started/stopped (push-to-talk) rather than gated by
            # our own real-time VAD.
            vad_filter=True,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()


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
    or more events produced by that frame — usually empty, occasionally
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
            return []  # too short, likely a noise blip — drop it

        audio = np.concatenate(buffer).astype(np.float32)
        text = self.transcriber.transcribe(audio)
        if not text:
            return []
        return [{"type": "text", "text": text}]
