"""Settings' speed test: you read one sentence, then every speech model that
is already on this PC transcribes that same recording, and the dialog shows
how long each took and what it heard.

Model speed depends far more on the PC than on anything a label can say (a
large model that takes 14 s on one laptop's processor takes well under a
second on a strong graphics card), so the honest answer is to measure it on
the user's own machine, with their own mic and voice.

Nothing is downloaded (models load with local_files_only) and nothing is
saved: the recording lives in memory only while the dialog is open.
"""

from __future__ import annotations

import gc
import time

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core import settings as hotkey_settings
from core.audio_capture import (
    SAMPLE_RATE,
    chunk_level,
    device_native_samplerate,
    resample_to_16k,
    resolve_input_device,
)

SENTENCE = (
    "Please send the updated invoice to Maria before Friday, "
    "and copy the whole team on the email."
)
MAX_RECORD_SEC = 12


def short_model_name(size: str) -> str:
    """"Very accurate: Large turbo, about 3x slower..." -> "Large turbo"."""
    label = dict(hotkey_settings.AVAILABLE_MODEL_SIZES).get(size, size)
    name = label.split(":", 1)[-1]
    return name.split(",")[0].split("(")[0].strip()


class SpeedTestThread(QThread):
    """Runs each model on the recording, one after another, and reports as it
    goes. Each model is loaded, timed and dropped before the next one, so at
    most one extra model is in memory at a time."""

    started_model = Signal(str)
    result = Signal(str, float, str)  # size, seconds, text heard
    failed = Signal(str, str)  # size, message

    def __init__(self, sizes: list[str], audio: np.ndarray, current, current_size: str) -> None:  # noqa: ANN001
        super().__init__()
        self.sizes = sizes
        self.audio = audio
        self.current = current
        self.current_size = current_size
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        from core.transcribe import Transcriber

        language = hotkey_settings.get_language()
        for size in self.sizes:
            if self._stop:
                return
            self.started_model.emit(size)
            try:
                if size == self.current_size and self.current is not None:
                    model = self.current
                else:
                    model = Transcriber(size, local_files_only=True)
                # One untimed warm-up pass on a short slice, so the first
                # model is not penalised for one-time start-up work.
                model.transcribe(self.audio[: SAMPLE_RATE], language=language)
                start = time.monotonic()
                text = model.transcribe(self.audio, language=language)
                seconds = time.monotonic() - start
                self.result.emit(size, seconds, text)
            except Exception as exc:  # noqa: BLE001
                self.failed.emit(size, str(exc))
            finally:
                model = None
                gc.collect()


class SpeedTestDialog(QDialog):
    def __init__(self, stylesheet: str, current_transcriber, parent: QWidget | None = None) -> None:  # noqa: ANN001
        super().__init__(parent)
        from core.transcribe import is_model_downloaded

        self.setWindowTitle("Speed test")
        self.setStyleSheet(stylesheet)
        self.setMinimumWidth(560)
        self._current = current_transcriber
        self._current_size = hotkey_settings.get_model_size()
        self._downloaded = [
            size
            for size, _ in hotkey_settings.AVAILABLE_MODEL_SIZES
            if is_model_downloaded(size)
        ]
        self._stream: sd.InputStream | None = None
        self._chunks: list[np.ndarray] = []
        self._rate = SAMPLE_RATE
        self._level = 0.0
        self._started_at = 0.0
        self._worker: SpeedTestThread | None = None
        self._times: dict[str, float] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(10)

        title = QLabel("How fast is each model on this PC?")
        title.setStyleSheet("font-size: 17px; font-weight: 700; color: #eceef4;")
        layout.addWidget(title)
        intro = QLabel(
            "Read the sentence below out loud. VoxScribe then runs every speech model "
            "already downloaded on that same recording and shows how long each one "
            "took. Nothing is downloaded or saved."
        )
        intro.setWordWrap(True)
        intro.setObjectName("settingsHint")
        layout.addWidget(intro)

        sentence = QLabel(f"“{SENTENCE}”")
        sentence.setWordWrap(True)
        sentence.setStyleSheet(
            "background: #1b1d27; border: 1px solid #2b2e3b; border-radius: 10px;"
            "padding: 12px 14px; color: #eceef4; font-size: 14px; font-weight: 600;"
        )
        layout.addWidget(sentence)

        record_row = QHBoxLayout()
        self._record_button = QPushButton("Start recording")
        self._record_button.setMinimumHeight(36)
        self._record_button.setStyleSheet(
            "QPushButton { background: #3ecf8e; color: #0b2418; border: none;"
            " border-radius: 9px; padding: 8px 18px; font-weight: 700; }"
            "QPushButton:hover { background: #4ee0a0; }"
            "QPushButton:disabled { background: #2b2e3b; color: #8b8d9c; }"
        )
        self._record_button.clicked.connect(self._toggle_recording)
        record_row.addWidget(self._record_button)
        self._meter = QProgressBar()
        self._meter.setRange(0, 100)
        self._meter.setTextVisible(False)
        self._meter.setFixedHeight(8)
        self._meter.setStyleSheet(
            "QProgressBar { background: #1b1d27; border: 1px solid #2b2e3b; border-radius: 4px; }"
            "QProgressBar::chunk { background: #3ecf8e; border-radius: 3px; }"
        )
        record_row.addWidget(self._meter, 1)
        self._record_status = QLabel("")
        self._record_status.setObjectName("settingsHint")
        record_row.addWidget(self._record_status)
        layout.addLayout(record_row)

        self._grid = QGridLayout()
        self._grid.setHorizontalSpacing(14)
        self._grid.setVerticalSpacing(8)
        self._rows: dict[str, tuple[QLabel, QProgressBar, QLabel]] = {}
        for row, (size, _) in enumerate(hotkey_settings.AVAILABLE_MODEL_SIZES):
            name = short_model_name(size)
            if size == self._current_size:
                name += "  (in use)"
            name_label = QLabel(name)
            name_label.setStyleSheet("color: #eceef4; font-weight: 600;")
            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setValue(0)
            bar.setTextVisible(False)
            bar.setFixedHeight(8)
            bar.setStyleSheet(
                "QProgressBar { background: #1b1d27; border: none; border-radius: 4px; }"
                "QProgressBar::chunk { background: #3ecf8e; border-radius: 4px; }"
            )
            status = QLabel("Ready to test" if size in self._downloaded else "Not downloaded")
            status.setObjectName("settingsHint")
            status.setWordWrap(True)
            self._grid.addWidget(name_label, row, 0)
            self._grid.addWidget(bar, row, 1)
            self._grid.addWidget(status, row, 2)
            self._rows[size] = (name_label, bar, status)
        self._grid.setColumnStretch(1, 1)
        self._grid.setColumnStretch(2, 2)
        layout.addLayout(self._grid)

        self._heard = QLabel("")
        self._heard.setWordWrap(True)
        self._heard.setObjectName("settingsHint")
        layout.addWidget(self._heard)

        note = QLabel(
            "Times are for this PC's processor. Shorter is better: it is roughly how "
            "long you wait after letting go of the hotkey for a sentence like this. "
            "The model in use only changes if you pick another one in Settings."
        )
        note.setWordWrap(True)
        note.setObjectName("settingsHint")
        layout.addWidget(note)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close = QPushButton("Close")
        close.setMinimumHeight(34)
        close.setStyleSheet(
            "QPushButton { background: #1b1d27; color: #eceef4; border: 1px solid #2b2e3b;"
            " border-radius: 9px; padding: 6px 20px; font-weight: 600; }"
            "QPushButton:hover { background: #22242f; }"
        )
        close.clicked.connect(self.reject)
        close_row.addWidget(close)
        layout.addLayout(close_row)

        self._tick = QTimer(self)
        self._tick.setInterval(50)
        self._tick.timeout.connect(self._on_tick)

        if not self._downloaded:
            self._record_button.setEnabled(False)
            self._record_status.setText("No models downloaded yet.")

    # -- recording -------------------------------------------------------------

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
            self._record_status.setText(f"No microphone: {exc}")
            return
        self._started_at = time.monotonic()
        self._record_button.setText("Stop and test")
        self._record_status.setText("Recording...")
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
            self._record_button.setText("Start recording")
            self._record_status.setText("Too short. Read the whole sentence.")
            return
        self._run_tests(audio)

    def _on_tick(self) -> None:
        self._meter.setValue(int(self._level * 100))
        self._level *= 0.6
        elapsed = time.monotonic() - self._started_at
        self._record_status.setText(f"Recording... {elapsed:.0f} s")
        if elapsed >= MAX_RECORD_SEC:
            self._stop_recording()

    # -- testing ---------------------------------------------------------------

    def _run_tests(self, audio: np.ndarray) -> None:
        self._record_button.setEnabled(False)
        self._record_button.setText("Testing...")
        self._record_status.setText(f"{len(audio) / SAMPLE_RATE:.1f} s recorded")
        self._times = {}
        for size in self._downloaded:
            _, bar, status = self._rows[size]
            bar.setValue(0)
            status.setText("Waiting")
        self._worker = SpeedTestThread(
            self._downloaded, audio, self._current, self._current_size
        )
        self._worker.started_model.connect(self._on_started_model)
        self._worker.result.connect(self._on_result)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_started_model(self, size: str) -> None:
        self._rows[size][2].setText("Testing... (loading the model can take a moment)")

    def _on_result(self, size: str, seconds: float, text: str) -> None:
        self._times[size] = seconds
        self._rows[size][2].setText(f"{seconds:.1f} s")
        self._rows[size][2].setStyleSheet("color: #eceef4; font-weight: 700;")
        slowest = max(self._times.values())
        for done, value in self._times.items():
            self._rows[done][1].setValue(int(1000 * value / slowest))
        if size == self._current_size or not self._heard.text():
            self._heard.setText(f"{short_model_name(size)} heard: “{text}”")

    def _on_failed(self, size: str, message: str) -> None:
        self._rows[size][2].setText("Could not load")
        self._rows[size][2].setToolTip(message)

    def _on_finished(self) -> None:
        self._record_button.setEnabled(True)
        self._record_button.setText("Test again")
        if self._times:
            fastest = min(self._times, key=self._times.get)
            self._record_status.setText(f"Fastest here: {short_model_name(fastest)}")

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
            # Let the current model finish rather than kill a native call mid-way.
            self._worker.stop()
            self._worker.wait()
        super().reject()
