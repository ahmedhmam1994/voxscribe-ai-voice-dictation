"""Settings' "Teach VoxScribe your voice": you read a short script, VoxScribe
transcribes each sentence with the speech model you use now, and then lists the
known words (drug names, legal and business terms, your own vocabulary) it
heard differently from how you meant them. You tick the ones to keep, and they
become word replacements ("levoseroxine" -> "levothyroxine").

Everything stays on this PC: the recordings live in memory only while the
dialog is open, and nothing is downloaded or sent. The logic that compares what
was meant with what was heard is in core/voice_teach.py.
"""

from __future__ import annotations

import time

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core import replacements, term_packs, voice_teach
from core import settings as hotkey_settings
from core.audio_capture import (
    SAMPLE_RATE,
    chunk_level,
    device_native_samplerate,
    resample_to_16k,
    resolve_input_device,
)

MAX_RECORD_SEC = 20

_PRIMARY = (
    "QPushButton { background: #3ecf8e; color: #0b2418; border: none;"
    " border-radius: 9px; padding: 8px 18px; font-weight: 700; }"
    "QPushButton:hover { background: #4ee0a0; }"
    "QPushButton:disabled { background: #2b2e3b; color: #8b8d9c; }"
)
_SECONDARY = (
    "QPushButton { background: #1b1d27; color: #eceef4; border: 1px solid #2b2e3b;"
    " border-radius: 9px; padding: 6px 18px; font-weight: 600; }"
    "QPushButton:hover { background: #22242f; }"
    "QPushButton:disabled { color: #5c5e6c; }"
)


class _TranscribeThread(QThread):
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, transcriber, audio: np.ndarray, prompt: str | None) -> None:  # noqa: ANN001
        super().__init__()
        self._transcriber = transcriber
        self._audio = audio
        self._prompt = prompt

    def run(self) -> None:
        try:
            text = self._transcriber.transcribe(
                self._audio, language="en", initial_prompt=self._prompt, task="transcribe",
                beam_size=1,
            )
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.done.emit(text)


class TeachDialog(QDialog):
    """After it closes, `accepted_pairs` holds the (heard, replacement) pairs the
    person chose to add; the caller merges them into the word replacements."""

    def __init__(self, stylesheet: str, transcriber, parent: QWidget | None = None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.setWindowTitle("Teach VoxScribe your voice")
        self.setStyleSheet(stylesheet)
        self.setMinimumWidth(580)
        self.accepted_pairs: list[tuple[str, str]] = []
        self._transcriber = transcriber
        self._script = voice_teach.build_script(
            hotkey_settings.get_enabled_packs(), hotkey_settings.get_custom_vocabulary()
        )
        self._known = term_packs.combined_terms(
            hotkey_settings.get_enabled_packs() or [p for p, _ in term_packs.BUILTIN_PACKS],
            hotkey_settings.get_custom_vocabulary(),
        )
        self._index = 0
        self._slips: dict[int, list[voice_teach.Slip]] = {}
        self._stream: sd.InputStream | None = None
        self._chunks: list[np.ndarray] = []
        self._rate = SAMPLE_RATE
        self._level = 0.0
        self._started_at = 0.0
        self._worker: _TranscribeThread | None = None
        self._boxes: list[tuple[QCheckBox, voice_teach.Proposal]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(10)

        title = QLabel("Teach VoxScribe your voice")
        title.setStyleSheet("font-size: 17px; font-weight: 700; color: #eceef4;")
        layout.addWidget(title)
        self._intro = QLabel(
            "Read each sentence out loud, one at a time, at your normal pace. VoxScribe "
            "listens with the speech model you use now, then shows the words it "
            "misheard in your voice and offers to correct them from then on. It takes "
            "about three minutes. Recordings stay on this PC and are not saved."
        )
        self._intro.setWordWrap(True)
        self._intro.setObjectName("settingsHint")
        layout.addWidget(self._intro)

        self._reading = QWidget()
        reading = QVBoxLayout(self._reading)
        reading.setContentsMargins(0, 0, 0, 0)
        reading.setSpacing(10)
        self._step = QLabel("")
        self._step.setStyleSheet("color: #8b8d9c; font-weight: 600;")
        reading.addWidget(self._step)
        self._sentence = QLabel("")
        self._sentence.setWordWrap(True)
        self._sentence.setStyleSheet(
            "background: #1b1d27; border: 1px solid #2b2e3b; border-radius: 10px;"
            "padding: 12px 14px; color: #eceef4; font-size: 15px; font-weight: 600;"
        )
        reading.addWidget(self._sentence)

        record_row = QHBoxLayout()
        self._record = QPushButton("Start recording")
        self._record.setMinimumHeight(36)
        self._record.setStyleSheet(_PRIMARY)
        self._record.clicked.connect(self._toggle_recording)
        record_row.addWidget(self._record)
        self._meter = QProgressBar()
        self._meter.setRange(0, 100)
        self._meter.setTextVisible(False)
        self._meter.setFixedHeight(8)
        self._meter.setStyleSheet(
            "QProgressBar { background: #1b1d27; border: 1px solid #2b2e3b; border-radius: 4px; }"
            "QProgressBar::chunk { background: #3ecf8e; border-radius: 3px; }"
        )
        record_row.addWidget(self._meter, 1)
        self._status = QLabel("")
        self._status.setObjectName("settingsHint")
        record_row.addWidget(self._status)
        reading.addLayout(record_row)

        self._heard = QLabel("")
        self._heard.setWordWrap(True)
        self._heard.setObjectName("settingsHint")
        reading.addWidget(self._heard)

        nav = QHBoxLayout()
        self._skip = QPushButton("Skip this one")
        self._skip.setStyleSheet(_SECONDARY)
        self._skip.setMinimumHeight(34)
        self._skip.clicked.connect(self._next)
        self._next_button = QPushButton("Next sentence")
        self._next_button.setStyleSheet(_SECONDARY)
        self._next_button.setMinimumHeight(34)
        self._next_button.clicked.connect(self._next)
        self._next_button.setEnabled(False)
        nav.addWidget(self._skip)
        nav.addStretch(1)
        nav.addWidget(self._next_button)
        reading.addLayout(nav)
        layout.addWidget(self._reading)

        self._results = QWidget()
        results = QVBoxLayout(self._results)
        results.setContentsMargins(0, 0, 0, 0)
        results.setSpacing(8)
        self._results_text = QLabel("")
        self._results_text.setWordWrap(True)
        self._results_text.setObjectName("settingsHint")
        results.addWidget(self._results_text)
        self._list_holder = QWidget()
        self._list_layout = QVBoxLayout(self._list_holder)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(6)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setMaximumHeight(260)
        scroll.setWidget(self._list_holder)
        results.addWidget(scroll)
        self._results.setVisible(False)
        layout.addWidget(self._results)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self._add = QPushButton("Add selected to my word fixes")
        self._add.setStyleSheet(_PRIMARY)
        self._add.setMinimumHeight(34)
        self._add.clicked.connect(self._accept_selected)
        self._add.setVisible(False)
        self._close = QPushButton("Cancel")
        self._close.setStyleSheet(_SECONDARY)
        self._close.setMinimumHeight(34)
        self._close.clicked.connect(self.reject)
        bottom.addWidget(self._add)
        bottom.addWidget(self._close)
        layout.addLayout(bottom)

        self._tick = QTimer(self)
        self._tick.setInterval(50)
        self._tick.timeout.connect(self._on_tick)
        self._show_sentence()

    # -- script ------------------------------------------------------------------

    def _show_sentence(self) -> None:
        sentence, _terms = self._script[self._index]
        self._step.setText(f"Sentence {self._index + 1} of {len(self._script)}")
        self._sentence.setText(f"“{sentence}”")
        self._heard.setText("")
        self._status.setText("")
        self._record.setText("Start recording")
        self._record.setEnabled(True)
        self._next_button.setEnabled(False)
        self._next_button.setText(
            "See results" if self._index == len(self._script) - 1 else "Next sentence"
        )
        self._skip.setEnabled(True)

    def _next(self) -> None:
        if self._index >= len(self._script) - 1:
            self._show_results()
            return
        self._index += 1
        self._show_sentence()

    # -- recording ---------------------------------------------------------------

    def _toggle_recording(self) -> None:
        if self._stream is None:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self) -> None:
        device = resolve_input_device(hotkey_settings.get_input_device())
        self._rate = device_native_samplerate(device)
        self._chunks = []

        def callback(indata, frames, time_info, status):  # noqa: ANN001
            chunk = indata[:, 0].copy()
            self._chunks.append(chunk)
            level = chunk_level(chunk)
            if level > self._level:
                self._level = level

        try:
            self._stream = sd.InputStream(
                samplerate=self._rate, channels=1, dtype="float32", device=device,
                callback=callback,
            )
            self._stream.start()
        except Exception as exc:  # noqa: BLE001
            self._stream = None
            self._status.setText(f"No microphone: {exc}")
            return
        self._started_at = time.monotonic()
        self._record.setText("Stop")
        self._status.setText("Recording...")
        self._skip.setEnabled(False)
        self._next_button.setEnabled(False)
        self._tick.start()

    def _stop_recording(self) -> None:
        stream, self._stream = self._stream, None
        self._tick.stop()
        self._meter.setValue(0)
        try:
            stream.stop()
            stream.close()
        except Exception:  # noqa: BLE001
            pass
        audio = np.concatenate(self._chunks) if self._chunks else np.zeros(0, np.float32)
        audio = resample_to_16k(audio, self._rate)
        self._chunks = []
        if len(audio) < SAMPLE_RATE:
            self._record.setText("Start recording")
            self._status.setText("Too short. Read the whole sentence.")
            self._skip.setEnabled(True)
            return
        self._record.setEnabled(False)
        self._record.setText("Listening...")
        self._status.setText(f"{len(audio) / SAMPLE_RATE:.1f} s recorded")
        self._worker = _TranscribeThread(
            self._transcriber, audio, hotkey_settings.custom_vocabulary_prompt()
        )
        self._worker.done.connect(self._on_heard)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_tick(self) -> None:
        self._meter.setValue(int(self._level * 100))
        self._level *= 0.6
        elapsed = time.monotonic() - self._started_at
        self._status.setText(f"Recording... {elapsed:.0f} s")
        if elapsed >= MAX_RECORD_SEC:
            self._stop_recording()

    # -- what was heard ----------------------------------------------------------

    def _fixed_like_dictation(self, raw: str) -> str:
        """The text as VoxScribe would type it now, so only slips that are still
        there are offered."""
        text = replacements.apply_replacements(raw)
        return term_packs.correct_text(
            text, hotkey_settings.correction_terms(), hotkey_settings.correction_fuzzy_terms()
        )

    def _on_heard(self, raw: str) -> None:
        sentence, terms = self._script[self._index]
        heard = self._fixed_like_dictation(raw)
        slips = voice_teach.find_slips(sentence, terms, heard, self._known)
        self._slips[self._index] = slips
        if not heard.strip():
            self._heard.setText("VoxScribe heard nothing. Try again, a little closer to the mic.")
        elif slips:
            wrong = ", ".join(f"“{s.heard}” (meant {s.expected})" for s in slips)
            self._heard.setText(f"Heard: “{heard}”\nMisheard: {wrong}")
        else:
            self._heard.setText(f"Heard: “{heard}”\nAll the key words were right.")
        self._record.setEnabled(True)
        self._record.setText("Record again")
        self._skip.setEnabled(True)
        self._next_button.setEnabled(bool(heard.strip()))

    def _on_failed(self, message: str) -> None:
        self._heard.setText(f"Could not transcribe: {message}")
        self._record.setEnabled(True)
        self._record.setText("Start recording")
        self._skip.setEnabled(True)

    # -- results -----------------------------------------------------------------

    def _show_results(self) -> None:
        proposals = voice_teach.merge(list(self._slips.values()))
        recorded = len(self._slips)
        self._reading.setVisible(False)
        self._intro.setVisible(False)
        self._results.setVisible(True)
        self._close.setText("Close")
        if recorded == 0:
            self._results_text.setText(
                "No sentences were recorded, so there is nothing to learn yet."
            )
            return
        if not proposals:
            self._results_text.setText(
                f"VoxScribe understood all the key words in {recorded} "
                f"sentence{'s' if recorded != 1 else ''}. Nothing to fix."
            )
            return
        self._results_text.setText(
            "These words came out differently from what you meant. Tick the ones to fix "
            "from now on. A fix changes that word everywhere you dictate, so untick any "
            "that is a real word you also use."
        )
        for proposal in proposals:
            box = QCheckBox(f"“{proposal.heard}”  →  {proposal.expected}")
            box.setChecked(True)
            self._list_layout.addWidget(box)
            self._boxes.append((box, proposal))
        self._list_layout.addStretch(1)
        self._add.setVisible(True)

    def _accept_selected(self) -> None:
        self.accepted_pairs = [
            (p.heard, p.expected) for box, p in self._boxes if box.isChecked()
        ]
        self.accept()

    def reject(self) -> None:  # noqa: D102
        if self._stream is not None:
            self._tick.stop()
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:  # noqa: BLE001
                pass
            self._stream = None
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait()
        super().reject()
