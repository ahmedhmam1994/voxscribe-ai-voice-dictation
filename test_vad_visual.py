"""Standalone visual VAD test window (throwaway test tool, not part of the app).

Shows live speech/silence status and the raw probability, with a gain slider
you can drag to tune sensitivity for your mic in real time.
"""
import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QProgressBar, QVBoxLayout, QWidget, QSlider,
)
from PySide6.QtCore import QTimer, Qt

from core.audio_capture import frames
from core.vad import SileroVAD


class VADVisualWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VAD Test")
        self.resize(460, 220)

        self.vad = SileroVAD()
        self.gen = frames()

        central = QWidget()
        layout = QVBoxLayout(central)

        self.status = QLabel("SILENCE")
        self.status.setStyleSheet("font-size: 28px; font-weight: bold; color: gray;")
        self.status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status)

        self.prob_label = QLabel("probability: 0.00")
        layout.addWidget(self.prob_label)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        layout.addWidget(self.bar)

        layout.addWidget(QLabel("Gain (drag to increase sensitivity):"))
        self.gain_slider = QSlider(Qt.Horizontal)
        self.gain_slider.setRange(1, 100)
        self.gain_slider.setValue(int(self.vad.gain))
        self.gain_slider.valueChanged.connect(self.on_gain_changed)
        layout.addWidget(self.gain_slider)

        self.gain_label = QLabel("gain: 20")
        layout.addWidget(self.gain_label)

        self.setCentralWidget(central)

        self.timer = QTimer()
        self.timer.timeout.connect(self.poll)
        self.timer.start(1)

    def on_gain_changed(self, value):
        self.vad.gain = float(value)
        self.gain_label.setText(f"gain: {value}")

    def poll(self):
        try:
            frame = next(self.gen)
        except StopIteration:
            return
        prob = self.vad.speech_probability(frame)
        self.prob_label.setText(f"probability: {prob:.3f}")
        self.bar.setValue(int(prob * 100))
        if prob >= self.vad.threshold:
            self.status.setText("SPEECH")
            self.status.setStyleSheet("font-size: 28px; font-weight: bold; color: green;")
        else:
            self.status.setText("SILENCE")
            self.status.setStyleSheet("font-size: 28px; font-weight: bold; color: gray;")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VADVisualWindow()
    window.show()
    sys.exit(app.exec())
