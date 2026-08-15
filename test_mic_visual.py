"""Standalone visual mic-level test window (throwaway test tool, not part of the app)."""
import sys
import numpy as np
import sounddevice as sd
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QProgressBar, QVBoxLayout, QWidget
from PySide6.QtCore import QTimer

SAMPLE_RATE = 16000
BLOCK_SIZE = 1024

class MicMeterWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mic Level Test")
        self.resize(420, 160)

        central = QWidget()
        layout = QVBoxLayout(central)

        self.label = QLabel("Talk into your mic. The bar below should move.")
        self.label.setWordWrap(True)
        layout.addWidget(self.label)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        layout.addWidget(self.bar)

        self.status = QLabel("Listening...")
        layout.addWidget(self.status)

        self.setCentralWidget(central)

        self.level = 0.0
        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            blocksize=BLOCK_SIZE,
            dtype="float32",
            callback=self.audio_callback,
        )
        self.stream.start()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(50)

    def audio_callback(self, indata, frames, time_info, status):
        rms = float(np.sqrt(np.mean(indata**2)))
        self.level = max(self.level * 0.6, rms)

    def update_ui(self):
        percent = min(int(self.level * 2000), 100)
        self.bar.setValue(percent)
        if percent > 5:
            self.status.setText("Sound detected!")
        else:
            self.status.setText("Listening... (say something)")
        self.level *= 0.7

    def closeEvent(self, event):
        self.stream.stop()
        self.stream.close()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MicMeterWindow()
    window.show()
    sys.exit(app.exec())
