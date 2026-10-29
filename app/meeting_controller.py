"""Runs a meeting from the Qt side: starts and stops the two-track recorder
(core/meeting_recorder.py), then, in a background thread, transcribes both tracks,
merges them and writes the note (core/meeting.py, core/meeting_notes.py).

States: "idle", "recording", "processing". The window listens to the signals and
only has to show them.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from core import meeting_notes, meeting_recorder
from core import settings as hotkey_settings
from core.meeting import transcribe_meeting

TEMP_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "VoxScribe" / "meetings" / "tmp"
STALE_AFTER_SECONDS = 7 * 24 * 3600

IDLE = "idle"
RECORDING = "recording"
PROCESSING = "processing"


class MeetingWorker(QThread):
    """Turns the recordings into a saved note. The recordings are deleted only after
    the note is written; if anything fails they stay, and `failed` says where."""

    progress = Signal(float)
    done = Signal(object)  # the note's Path
    failed = Signal(str, object)  # message, the MeetingAudio

    def __init__(  # noqa: ANN204
        self,
        transcriber,  # noqa: ANN001
        audio,  # noqa: ANN001
        language: str | None,
        prompt: str | None,
        postprocess: Callable[[str], str],
        started: datetime,
        folder: Path,
    ):
        super().__init__()
        self._transcriber = transcriber
        self._audio = audio
        self._language = language
        self._prompt = prompt
        self._postprocess = postprocess
        self._started = started
        self._folder = folder

    def run(self) -> None:
        audio = self._audio
        try:
            lines = transcribe_meeting(
                self._transcriber,
                audio.mic_path,
                audio.others_path,
                self._language,
                self._prompt,
                self._postprocess,
                self.progress.emit,
            )
            note = meeting_notes.build_note(
                lines, self._started, audio.seconds, with_others=audio.others_path is not None
            )
            path = meeting_notes.save_note(self._folder, note, self._started)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc), audio)
            return
        meeting_recorder.delete_audio(audio)
        self.done.emit(path)


class MeetingController(QObject):
    state_changed = Signal(str)
    tick = Signal(float, float, float)  # elapsed seconds, microphone level, others level
    progress = Signal(float)
    saved = Signal(object)  # the note's Path
    failed = Signal(str)

    def __init__(  # noqa: ANN204
        self,
        parent,  # noqa: ANN001
        get_transcriber: Callable[[], object],
        postprocess: Callable[[str], str],
    ):
        super().__init__(parent)
        self._get_transcriber = get_transcriber
        self._postprocess = postprocess
        self.state = IDLE
        self._recorder: meeting_recorder.MeetingRecorder | None = None
        self._worker: MeetingWorker | None = None
        self._started: datetime | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._on_tick)
        meeting_recorder.clean_stale(TEMP_DIR, STALE_AFTER_SECONDS)

    @property
    def busy(self) -> bool:
        return self.state != IDLE

    @property
    def has_loopback(self) -> bool:
        return bool(self._recorder and self._recorder.has_loopback)

    @property
    def loopback_error(self) -> str | None:
        return self._recorder.loopback_error if self._recorder else None

    def _set_state(self, state: str) -> None:
        self.state = state
        self.state_changed.emit(state)

    def start(self, use_loopback: bool = True) -> str | None:
        """Starts recording. Returns an error message, or None when it started."""
        if self.busy:
            return "A meeting is already being recorded."
        if self._get_transcriber() is None:
            return "The speech model is still loading. Try again in a moment."
        recorder = meeting_recorder.MeetingRecorder(
            TEMP_DIR, loopback_error=None if use_loopback else "Turned off in Settings"
        )
        try:
            recorder.start()
        except Exception as exc:  # noqa: BLE001
            return f"No microphone available: {exc}"
        self._recorder = recorder
        self._started = datetime.now()
        self._set_state(RECORDING)
        self._timer.start()
        return None

    def _on_tick(self) -> None:
        if self._recorder is not None and self._recorder.running:
            self.tick.emit(
                self._recorder.elapsed, self._recorder.mic_level, self._recorder.others_level
            )

    def stop(self) -> None:
        """Stops recording and starts writing the notes."""
        if self.state != RECORDING or self._recorder is None or self._started is None:
            return
        self._timer.stop()
        audio = self._recorder.stop()
        self._set_state(PROCESSING)
        self._worker = MeetingWorker(
            self._get_transcriber(),
            audio,
            hotkey_settings.get_language(),
            hotkey_settings.custom_vocabulary_prompt(),
            self._postprocess,
            self._started,
            Path(hotkey_settings.get_meeting_folder()),
        )
        self._worker.progress.connect(self.progress)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_done(self, path: object) -> None:
        self._worker = None
        self._set_state(IDLE)
        self.saved.emit(path)

    def _on_failed(self, message: str, audio: object) -> None:
        self._worker = None
        self._set_state(IDLE)
        kept = getattr(audio, "mic_path", None)
        where = f" The recording was kept in {kept.parent}." if kept else ""
        self.failed.emit(f"Could not write the meeting notes: {message}.{where}")

    def shutdown(self) -> None:
        """Called when the app quits: stops recording and keeps the audio (it is
        cleaned up after a week) instead of losing it silently."""
        if self.state == RECORDING and self._recorder is not None:
            self._timer.stop()
            self._recorder.stop()
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(60_000)


def elapsed_text(seconds: float) -> str:
    return meeting_notes.clock(seconds)
