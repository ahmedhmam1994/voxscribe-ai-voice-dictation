"""Push-to-talk transcription test (throwaway test tool, not part of the app).

Click Start, talk, click Stop -- whatever was recorded in between gets sent
to faster-whisper and the result appears in the text box. No automatic
speech detection involved, so it's unaffected by mic quality/quietness
issues that make real-time VAD unreliable.
"""
import sys

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.audio_capture import SAMPLE_RATE, _default_input_device
from core.transcribe import Transcriber


class ModelLoaderThread(QThread):
    done = Signal(object)
    failed = Signal(str)

    def run(self):
        try:
            t = Transcriber()
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.done.emit(t)


class TranscribeThread(QThread):
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, transcriber: Transcriber, audio: np.ndarray):
        super().__init__()
        self.transcriber = transcriber
        self.audio = audio

    def run(self):
        try:
            text = self.transcriber.transcribe(self.audio)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.done.emit(text)


class PTTWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Push-to-Talk Test")
        self.resize(520, 420)

        self.transcriber: Transcriber | None = None
        self.stream: sd.InputStream | None = None
        self._chunks: list[np.ndarray] = []

        central = QWidget()
        layout = QVBoxLayout(central)

        self.status = QLabel("Loading model...")
        self.status.setStyleSheet("font-size: 20px; font-weight: bold; color: gray;")
        layout.addWidget(self.status)

        self.button = QPushButton("Start")
        self.button.setEnabled(False)
        self.button.setStyleSheet("font-size: 18px; padding: 10px;")
        self.button.clicked.connect(self.toggle_recording)
        layout.addWidget(self.button)

        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setPlaceholderText("Transcribed text will appear here...")
        layout.addWidget(self.text_area)

        self.setCentralWidget(central)

        self.loader = ModelLoaderThread()
        self.loader.done.connect(self.on_model_loaded)
        self.loader.failed.connect(self.on_model_failed)
        self.loader.start()

    def on_model_loaded(self, transcriber: Transcriber):
        self.transcriber = transcriber
        self.status.setText("Ready")
        self.status.setStyleSheet("font-size: 20px; font-weight: bold; color: gray;")
        self.button.setEnabled(True)

    def on_model_failed(self, message: str):
        self.status.setText("Failed to load model")
        self.status.setStyleSheet("font-size: 20px; font-weight: bold; color: red;")
        self.text_area.append(f"[error] {message}")

    def toggle_recording(self):
        if self.stream is None:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        self._chunks = []
        device = _default_input_device()

        def callback(indata, frames, time_info, status):
            self._chunks.append(indata[:, 0].copy())

        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="float32", device=device, callback=callback
        )
        self.stream.start()
        self.button.setText("Stop")
        self.status.setText("Recording...")
        self.status.setStyleSheet("font-size: 20px; font-weight: bold; color: green;")

    def stop_recording(self):
        self.stream.stop()
        self.stream.close()
        self.stream = None
        self.button.setEnabled(False)
        self.button.setText("Start")
        self.status.setText("Transcribing...")
        self.status.setStyleSheet("font-size: 20px; font-weight: bold; color: orange;")

        audio = np.concatenate(self._chunks) if self._chunks else np.zeros(0, dtype=np.float32)
        self._chunks = []

        self.worker = TranscribeThread(self.transcriber, audio)
        self.worker.done.connect(self.on_transcribed)
        self.worker.failed.connect(self.on_transcribe_failed)
        self.worker.start()

    def on_transcribed(self, text: str):
        self.text_area.append(text if text else "[no speech recognized]")
        self.status.setText("Ready")
        self.status.setStyleSheet("font-size: 20px; font-weight: bold; color: gray;")
        self.button.setEnabled(True)

    def on_transcribe_failed(self, message: str):
        self.text_area.append(f"[error] {message}")
        self.status.setText("Ready")
        self.status.setStyleSheet("font-size: 20px; font-weight: bold; color: gray;")
        self.button.setEnabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PTTWindow()
    window.show()
    sys.exit(app.exec())
