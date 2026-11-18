"""The hands-free session's worker thread: mic in, phrases out (core/hands_free.py).

The mic callback only queues audio. This thread runs the speech detector on it,
cuts phrases at pauses and transcribes each one while the mic keeps queueing, so
nothing said during a transcription is lost. Each result goes to the window as a
signal; the window decides what to type (main_window.py, _on_hands_free_phrase).
"""

from __future__ import annotations

import queue
import threading
import traceback
from collections.abc import Callable
from datetime import datetime

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QThread, Signal

from core import hands_free
from core.audio_capture import RateMeter, device_native_samplerate
from core.crash_reporter import LOG_DIR
from core.vad import SileroVAD


class HandsFreeThread(QThread):
    # "listening" (waiting for speech), "hearing" (a phrase is being spoken),
    # "working" (a phrase is being transcribed).
    state = Signal(str)
    # text, the phrase's 16 kHz audio, seconds of speech in it
    phrase = Signal(str, object, float)
    # why the session ended: "stopped", "idle" or "error"
    ended = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        transcriber,  # noqa: ANN001 -- core.transcribe.Transcriber
        device: int | None,
        params: Callable[[], tuple[str | None, str | None, str]],
        level: Callable[[np.ndarray], None] | None = None,
        parent=None,  # noqa: ANN001
    ) -> None:
        super().__init__(parent)
        self._transcriber = transcriber
        self._device = device
        # (language, vocabulary prompt, task), read for every phrase so a change
        # in Settings or the tray applies at once.
        self._params = params
        self._level = level
        self._stop = threading.Event()
        self._typed: list[str] = []
        # A phrase that looked cut off mid-sentence, held to be joined with the
        # next one: (audio, text, speech_sec), and frames waited since.
        self._pending: tuple[np.ndarray, str, float] | None = None
        self._pending_wait = 0

    def _log_failure(self, exc: BaseException) -> None:
        """Writes what went wrong to the local logs folder (never sent anywhere)."""
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            with open(LOG_DIR / "hands_free.log", "a", encoding="utf-8") as f:
                f.write(f"--- {datetime.now():%Y-%m-%d %H:%M:%S} device={self._device}\n")
                f.write("".join(traceback.format_exception(exc)))
        except Exception:  # noqa: BLE001 -- logging must never raise
            pass

    def request_stop(self) -> None:
        self._stop.set()

    @property
    def stopping(self) -> bool:
        return self._stop.is_set()

    def note_typed(self, text: str) -> None:
        """What the window really typed, used as context for the next phrase."""
        self._typed.append(text)
        del self._typed[:-20]

    def run(self) -> None:
        audio_q: queue.Queue[np.ndarray] = queue.Queue()
        meter: RateMeter | None = None

        def callback(indata, frames, time_info, status) -> None:  # noqa: ANN001
            if meter is not None:
                meter.add(frames)
            chunk = indata[:, 0].copy()
            audio_q.put(chunk)
            if self._level is not None:
                self._level(chunk)

        try:
            vad = SileroVAD(threshold=hands_free.VAD_THRESHOLD, use_agc=True)
            meter = RateMeter(device_native_samplerate(self._device), self._device)
            _rate, stream = self._open(self._device, callback)
        except Exception as exc:  # noqa: BLE001
            self._log_failure(exc)
            self.failed.emit(str(exc) or type(exc).__name__)
            self.ended.emit("error")
            return

        # The first half second waits for the meter: some drivers send twice
        # the samples they report, and the resampler needs the real rate.
        resampler: hands_free.Resampler | None = None
        early: list[np.ndarray] = []
        segmenter = hands_free.Segmenter(vad.is_speech)
        hold_frames = round(hands_free.HOLD_SEC / hands_free.FRAME_SEC)
        reason = "stopped"
        self._pending = None
        self.state.emit("listening")
        try:
            while not self._stop.is_set():
                try:
                    chunk = audio_q.get(timeout=0.1)
                except queue.Empty:
                    continue
                if resampler is None:
                    early.append(chunk)
                    if not meter.measured:
                        continue
                    resampler = hands_free.Resampler(meter.rate())
                    chunk = np.concatenate(early)
                    early = []
                for frame in resampler.frames(chunk):
                    events = segmenter.push(frame)
                    if self._handle(events):
                        reason = "idle"
                        self._stop.set()
                        break
                    if self._pending is not None and not segmenter.in_phrase:
                        # Nothing followed a phrase that looked cut off: type it as is.
                        self._pending_wait += 1
                        if self._pending_wait >= hold_frames:
                            self._emit_pending()
                            self.state.emit("listening")
            if reason == "stopped":
                # Words still being said when the session is stopped are typed too.
                self._handle(segmenter.flush())
            self._emit_pending()
        except Exception as exc:  # noqa: BLE001
            self._log_failure(exc)
            self.failed.emit(str(exc) or type(exc).__name__)
            reason = "error"
        finally:
            try:
                stream.stop()
                stream.close()
            except Exception:  # noqa: BLE001 -- the device may already be gone
                pass
        self.ended.emit(reason)

    @staticmethod
    def _open(device: int | None, callback) -> tuple[int, sd.InputStream]:  # noqa: ANN001
        rate = device_native_samplerate(device)
        stream = sd.InputStream(
            samplerate=rate, channels=1, dtype="float32", device=device, callback=callback
        )
        stream.start()
        return rate, stream

    def _transcribe(self, audio: np.ndarray) -> str:
        language, vocabulary, task = self._params()
        text = self._transcriber.transcribe(
            audio,
            language=language,
            initial_prompt=hands_free.context_prompt(vocabulary, self._typed),
            task=task,
        )
        text = (text or "").strip()
        if hands_free.repeats_typed_end(text, self._typed):
            # Most likely the prompt written out again, not speech: decode once
            # more without the typed text (see core/hands_free.py).
            text = self._transcriber.transcribe(
                audio, language=language, initial_prompt=vocabulary or None, task=task
            )
            text = (text or "").strip()
        return text

    def _emit_pending(self) -> None:
        if self._pending is not None:
            audio, text, speech_sec = self._pending
            self._pending = None
            self.phrase.emit(text, audio, speech_sec)

    def _handle(self, events: list[tuple]) -> bool:
        """Acts on the segmenter's events; True when the session went idle."""
        for event in events:
            if event[0] == "start":
                self.state.emit("hearing")
            elif event[0] == "idle":
                return True
            elif event[0] == "phrase":
                self.state.emit("working")
                self._on_phrase(event[1], event[2])
                if not self._stop.is_set():
                    self.state.emit("listening")
        return False

    def _on_phrase(self, audio: np.ndarray, speech_sec: float) -> None:
        held = self._pending
        short = speech_sec <= hands_free.COMMAND_MAX_SPEECH_SEC
        # "Change Tuesday to Friday" is a few words longer than the other
        # commands, so it gets a little more time.
        maybe_change = speech_sec <= hands_free.CHANGE_MAX_SPEECH_SEC
        text = self._transcribe(audio) if held is None or short or maybe_change else ""
        command = (short and hands_free.match_command(text) is not None) or (
            maybe_change and hands_free.change_command(text) is not None
        )
        if text and (hands_free.is_stop_command(text) or command):
            # A command is never joined to the words before it: those are typed
            # first, as they were heard, then the command acts on them.
            self._emit_pending()
            self.phrase.emit(text, audio, speech_sec)
            return
        if held is not None:
            self._pending = None
            gap = np.zeros(int(0.3 * hands_free.SAMPLE_RATE), dtype=np.float32)
            joined = np.concatenate([held[0], gap, audio])
            if len(joined) <= hands_free.MAX_PHRASE_SEC * hands_free.SAMPLE_RATE:
                # One piece decodes far better than two halves of a sentence.
                audio, speech_sec = joined, held[2] + speech_sec
                text = self._transcribe(audio)
            else:
                self.phrase.emit(held[1], held[0], held[2])
                text = text or self._transcribe(audio)
        if text and hands_free.looks_unfinished(text) and not self._stop.is_set():
            self._pending = (audio, text, speech_sec)
            self._pending_wait = 0
            return
        self.phrase.emit(text, audio, speech_sec)
