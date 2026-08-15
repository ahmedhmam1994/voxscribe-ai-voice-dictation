"""Standalone visual transcription test window (throwaway test tool, not part of the app).

Shows a live status (Listening / Speech detected / Transcribing...) and
appends recognized text to a growing text area as speech segments are
detected and transcribed. Loads the faster-whisper model once at startup
(this can take a few seconds the first time, while it downloads).
"""
import sys

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.audio_capture import frames
from core.transcribe import SegmentingTranscriber


class ModelLoaderThread(QThread):
    """Loads the (possibly slow-to-download) whisper model off the UI thread."""

    done = Signal(object)
    failed = Signal(str)

    def run(self):
        try:
            st = SegmentingTranscriber()
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.done.emit(st)


class TranscribeVisualWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Transcription Test")
        self.resize(560, 420)

        self.segmenting_transcriber: SegmentingTranscriber | None = None
        self.gen = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.poll)

        central = QWidget()
        layout = QVBoxLayout(central)

        self.status = QLabel("Loading model...")
        self.status.setStyleSheet("font-size: 22px; font-weight: bold; color: gray;")
        self.status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status)

        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setPlaceholderText("Transcribed text will appear here...")
        layout.addWidget(self.text_area)

        self.setCentralWidget(central)

        self.loader = ModelLoaderThread()
        self.loader.done.connect(self.on_model_loaded)
        self.loader.failed.connect(self.on_model_failed)
        self.loader.start()

    def on_model_loaded(self, st: SegmentingTranscriber):
        self.segmenting_transcriber = st
        self.gen = frames()
        self.set_status("Listening", "gray")
        self.timer.start(1)

    def on_model_failed(self, message: str):
        self.set_status("Failed to load model", "red")
        self.text_area.append(f"[error] {message}")

    def set_status(self, text: str, color: str):
        self.status.setText(text)
        self.status.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {color};")

    def poll(self):
        if self.gen is None or self.segmenting_transcriber is None:
            return
        try:
            frame = next(self.gen)
        except StopIteration:
            return

        prob = self.segmenting_transcriber.vad.speech_probability(frame)
        if prob > 0.05:
            print(f"[debug] prob={prob:.3f}", flush=True)
        events = self.segmenting_transcriber.push(frame)
        for event in events:
            if event["type"] == "speech_start":
                self.set_status("Speech detected", "green")
            elif event["type"] == "speech_end":
                self.set_status("Transcribing...", "orange")
            elif event["type"] == "text":
                self.text_area.append(event["text"])
                self.set_status("Listening", "gray")

    def closeEvent(self, event):  # noqa: N802
        self.timer.stop()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TranscribeVisualWindow()
    window.show()
    sys.exit(app.exec())
