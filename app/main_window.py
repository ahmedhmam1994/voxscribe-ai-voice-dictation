"""Main window for the VoxScribe app.

Phase 4: real push-to-talk UI wired to the app's own core modules
(core/audio_capture.py, core/transcribe.py). Model loading happens on a
background QThread at startup, and each recording is transcribed on a
background QThread on Stop, so the UI never freezes. This follows the
pattern proven out in test_ptt_visual.py.
"""

from __future__ import annotations

import os
import webbrowser
from datetime import datetime
from pathlib import Path

import keyboard
import numpy as np
import sounddevice as sd
from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.floating_indicator import FloatingIndicator
from app.version import __version__
from core.audio_capture import (
    SAMPLE_RATE,
    _default_input_device,
    device_native_samplerate,
    resample_to_16k,
)
from core.cleanup import clean_transcript
from core.crash_reporter import LOG_DIR as CRASH_LOG_DIR
from core.transcribe import Transcriber
from core.updater import UpdateCheckThread, UpdateInfo

ICON_PATH = Path(__file__).parent / "icon.ico"
GLOBAL_HOTKEY = "f9"
UPDATE_CHECK_INTERVAL_MS = 7 * 24 * 60 * 60 * 1000  # weekly

# -- visual palette --------------------------------------------------------
# A cohesive dark theme (near-black surfaces, soft violet accent) rather than
# default battleship-gray Qt widgets. Chosen to feel like a focused, modern
# utility (in the spirit of Wispr Flow) without fighting Windows' own dark
# taskbar/tray rendering -- deep neutrals here read naturally next to it.
BG_WINDOW = "#121319"
BG_CARD = "#1b1d27"
BG_CARD_HOVER = "#22242f"
BORDER = "#2b2e3b"
BORDER_SOFT = "#242631"
TEXT_PRIMARY = "#eceef4"
TEXT_MUTED = "#8b8d9c"
TEXT_FAINT = "#5c5e6c"
ACCENT = "#8b7cf6"
ACCENT_HOVER = "#9d90f8"
ACCENT_PRESSED = "#7566e0"
ACCENT_DISABLED = "#3a3b4c"


class HotkeyBridge(QObject):
    """Relays the global hotkey (fired on a non-Qt background thread by the
    `keyboard` library) into the Qt event loop via signals. Qt auto-queues
    signal emissions across threads to the receiver's own thread, so this is
    the safe way to trigger GUI/audio code from the hotkey callback.

    Press/release are separate signals (rather than one toggle signal)
    because the global hotkey is now hold-to-talk: holding F9 down starts
    recording, releasing it stops and transcribes."""

    press_requested = Signal()
    release_requested = Signal()

STATUS_COLORS = {
    "loading": TEXT_MUTED,
    "ready": TEXT_MUTED,
    "recording": "#3ecf8e",  # green
    "transcribing": "#f0a54a",  # amber
    "error": "#f0546b",  # red
}

STATUS_LABEL_STYLE = (
    "font-size: 14px; font-weight: 600; letter-spacing: 0.2px; "
    "padding: 2px 0px; color: {color};"
)

MAIN_STYLESHEET = f"""
QMainWindow, QWidget#centralWidget {{
    background: {BG_WINDOW};
}}

QWidget {{
    font-family: "Segoe UI";
    font-size: 13px;
    color: {TEXT_PRIMARY};
}}

QLabel#transcriptCaption {{
    font-size: 11px;
    font-weight: 700;
    color: {TEXT_MUTED};
}}

QLabel#hotkeyHint {{
    font-size: 11px;
    color: {TEXT_FAINT};
}}

QPushButton#recordButton {{
    background: {ACCENT};
    color: #ffffff;
    font-size: 15px;
    font-weight: 700;
    border: none;
    border-radius: 12px;
    padding: 10px 16px;
}}
QPushButton#recordButton:hover {{
    background: {ACCENT_HOVER};
}}
QPushButton#recordButton:pressed {{
    background: {ACCENT_PRESSED};
}}
QPushButton#recordButton:disabled {{
    background: {ACCENT_DISABLED};
    color: {TEXT_FAINT};
}}
QPushButton#recordButton[recording="true"] {{
    background: #34b57a;
}}
QPushButton#recordButton[recording="true"]:hover {{
    background: #3ecf8e;
}}

QPushButton#secondaryButton {{
    background: {BG_CARD};
    color: {TEXT_PRIMARY};
    font-size: 13px;
    font-weight: 600;
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 8px 14px;
}}
QPushButton#secondaryButton:hover {{
    background: {BG_CARD_HOVER};
    border: 1px solid {ACCENT};
}}
QPushButton#secondaryButton:pressed {{
    background: {BORDER};
}}
QPushButton#secondaryButton:disabled {{
    color: {TEXT_FAINT};
    background: {BG_WINDOW};
    border: 1px solid {BORDER_SOFT};
}}

QTextEdit#transcriptArea {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 12px;
    font-size: 14px;
    line-height: 1.4;
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {TEXT_FAINT};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""


class ModelLoaderThread(QThread):
    done = Signal(object)
    failed = Signal(str)

    def run(self) -> None:
        try:
            transcriber = Transcriber()
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.done.emit(transcriber)


class TranscribeThread(QThread):
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, transcriber: Transcriber, audio: np.ndarray) -> None:
        super().__init__()
        self.transcriber = transcriber
        self.audio = audio

    def run(self) -> None:
        try:
            text = self.transcriber.transcribe(self.audio)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.done.emit(text)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("VoxScribe")
        self.resize(600, 560)
        self.setStyleSheet(MAIN_STYLESHEET)
        if ICON_PATH.exists():
            icon = QIcon(str(ICON_PATH))
            self.setWindowIcon(icon)
            QApplication.instance().setWindowIcon(icon)

        self.transcriber: Transcriber | None = None
        self.stream: sd.InputStream | None = None
        self._chunks: list[np.ndarray] = []
        self._record_rate: int = SAMPLE_RATE
        self._loader: ModelLoaderThread | None = None
        self._worker: TranscribeThread | None = None

        # Hold-to-talk state for the F9 global hotkey:
        # - _f9_key_down tracks the *physical* key state so repeated
        #   "press" events fired by key-repeat (common while holding a key
        #   down, depending on OS/driver) don't re-trigger start_recording.
        # - _hotkey_active_session tracks whether the *current* recording
        #   was started by the hotkey (vs. the on-screen button), so
        #   releasing F9 only stops a recording it actually started.
        self._f9_key_down = False
        self._hotkey_active_session = False

        # Small floating "recording/transcribing" pill -- see
        # app/floating_indicator.py. Hidden except while active.
        self._indicator = FloatingIndicator()

        # Don't quit the whole app just because MainWindow is hidden (tray
        # behavior); closeEvent() below hides rather than closes it anyway,
        # but this is a belt-and-suspenders safeguard.
        QApplication.instance().setQuitOnLastWindowClosed(False)

        central = QWidget(self)
        central.setObjectName("centralWidget")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 20, 20, 18)
        layout.setSpacing(14)

        self.status_label = QLabel("Loading model...")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setStyleSheet(
            STATUS_LABEL_STYLE.format(color=STATUS_COLORS["loading"])
        )
        layout.addWidget(self.status_label)

        self.record_button = QPushButton("Start Recording")
        self.record_button.setObjectName("recordButton")
        self.record_button.setProperty("recording", False)
        self.record_button.setEnabled(False)
        self.record_button.setMinimumHeight(48)
        self.record_button.setCursor(Qt.PointingHandCursor)
        self.record_button.clicked.connect(self.toggle_recording)
        layout.addWidget(self.record_button)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        self.save_button = QPushButton("Save Transcript")
        self.save_button.setObjectName("secondaryButton")
        self.save_button.setEnabled(False)
        self.save_button.setMinimumHeight(38)
        self.save_button.setCursor(Qt.PointingHandCursor)
        self.save_button.clicked.connect(self.save_transcript)
        button_row.addWidget(self.save_button)

        self.copy_button = QPushButton("Copy")
        self.copy_button.setObjectName("secondaryButton")
        self.copy_button.setEnabled(False)
        self.copy_button.setMinimumHeight(38)
        self.copy_button.setCursor(Qt.PointingHandCursor)
        self.copy_button.clicked.connect(self.copy_transcript)
        button_row.addWidget(self.copy_button)

        self.clear_button = QPushButton("Clear")
        self.clear_button.setObjectName("secondaryButton")
        self.clear_button.setEnabled(False)
        self.clear_button.setMinimumHeight(38)
        self.clear_button.setCursor(Qt.PointingHandCursor)
        self.clear_button.clicked.connect(self.clear_transcript)
        button_row.addWidget(self.clear_button)

        layout.addLayout(button_row)

        transcript_label = QLabel("TRANSCRIPT")
        transcript_label.setObjectName("transcriptCaption")
        layout.addWidget(transcript_label)

        self.transcript_area = QTextEdit()
        self.transcript_area.setObjectName("transcriptArea")
        self.transcript_area.setReadOnly(True)
        self.transcript_area.setFrameShape(QTextEdit.NoFrame)
        self.transcript_area.setPlaceholderText(
            "Click Start Recording, speak, then click Stop Recording. "
            "Your transcribed text will appear here."
        )
        self.transcript_area.textChanged.connect(self._update_save_button)
        layout.addWidget(self.transcript_area, stretch=1)

        self.setCentralWidget(central)

        self._loader = ModelLoaderThread()
        self._loader.done.connect(self._on_model_loaded)
        self._loader.failed.connect(self._on_model_load_failed)
        self._loader.start()

        # Global hold-to-talk hotkey: works even when this window isn't
        # focused (or is hidden to tray), so you can click into another
        # app's text field, hold the hotkey, talk, release it, and the
        # transcribed text gets typed directly into that field.
        self._hotkey_bridge = HotkeyBridge()
        self._hotkey_bridge.press_requested.connect(self._handle_hotkey_press)
        self._hotkey_bridge.release_requested.connect(self._handle_hotkey_release)
        self._hotkey_registration_error: str | None = None
        try:
            keyboard.on_press_key(
                GLOBAL_HOTKEY, lambda e: self._hotkey_bridge.press_requested.emit()
            )
            keyboard.on_release_key(
                GLOBAL_HOTKEY, lambda e: self._hotkey_bridge.release_requested.emit()
            )
            self._hotkey_hint = QLabel(
                f"Tip: hold {GLOBAL_HOTKEY.upper()} anywhere to talk — release to stop. "
                "The text will be typed directly into whatever you're focused on."
            )
            self._hotkey_hint.setObjectName("hotkeyHint")
            self._hotkey_hint.setWordWrap(True)
            self.centralWidget().layout().addWidget(self._hotkey_hint)
        except Exception as exc:  # noqa: BLE001
            # Global hooks can fail without admin rights on some systems;
            # the app still works fine via the on-screen button, but the
            # user needs to actually be told F9 won't work -- silently
            # swallowing this left them with no clue why dictating into
            # other apps never did anything.
            self._hotkey_registration_error = str(exc)
            self._hotkey_hint = QLabel(
                f"Global {GLOBAL_HOTKEY.upper()} hotkey unavailable "
                f"({exc}). Use the Start/Stop button below instead."
            )
            self._hotkey_hint.setObjectName("hotkeyHint")
            self._hotkey_hint.setWordWrap(True)
            self._hotkey_hint.setStyleSheet("color: #f0546b;")
            self.centralWidget().layout().addWidget(self._hotkey_hint)

        self._setup_tray_icon()

        self._update_checker: UpdateCheckThread | None = None
        self._pending_update_url: str | None = None
        # Silent on startup -- only surfaces a tray balloon if an update is
        # actually found. "Check for Updates..." in the tray menu re-runs
        # this with manual=True to also report "up to date"/failure.
        self._start_update_check(manual=False)

        # VoxScribe starts hidden to the tray and is meant to be left
        # running indefinitely -- without this, someone who never quits
        # the app would only ever get the startup check, once, and then
        # nothing for however long they leave it open. Re-checks weekly
        # for as long as the process stays alive (still not a substitute
        # for actually launching the app after a long-closed period).
        self._update_timer = QTimer(self)
        self._update_timer.setInterval(UPDATE_CHECK_INTERVAL_MS)
        self._update_timer.timeout.connect(lambda: self._start_update_check(manual=False))
        self._update_timer.start()

        # No tray to fall back on and the hotkey didn't register either --
        # the app would otherwise start invisible with no way for the user
        # to discover it's running or why F9 doesn't work. Show the window
        # so the warning label above is actually seen.
        if self._hotkey_registration_error and self.tray_icon is None:
            self._show_and_raise()

    # -- system tray ------------------------------------------------------

    def _setup_tray_icon(self) -> None:
        """Adds a tray icon so the app can keep running (F9 + indicator
        still work) after the main window is closed/hidden."""
        if not ICON_PATH.exists() or not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = None
            return

        self.tray_icon = QSystemTrayIcon(QIcon(str(ICON_PATH)), self)
        self.tray_icon.setToolTip("VoxScribe")

        menu = QMenu()
        show_action = QAction("Show Window", self)
        show_action.triggered.connect(self._show_and_raise)
        menu.addAction(show_action)

        check_updates_action = QAction("Check for Updates...", self)
        check_updates_action.triggered.connect(lambda: self._start_update_check(manual=True))
        menu.addAction(check_updates_action)

        logs_action = QAction("Open Logs Folder", self)
        logs_action.triggered.connect(self._open_logs_folder)
        menu.addAction(logs_action)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit_app)
        menu.addAction(quit_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.messageClicked.connect(self._on_tray_message_clicked)
        self.tray_icon.show()

        # The app now starts hidden (no window pops up on launch), so this
        # is the only cue that it's actually running -- and the only place
        # to tell the user the global hotkey didn't register, since that
        # failure happens before this tray icon even exists.
        if self._hotkey_registration_error:
            self.tray_icon.showMessage(
                "VoxScribe",
                f"Couldn't register the {GLOBAL_HOTKEY.upper()} hotkey (often needs "
                "admin rights). Open VoxScribe and use the Start/Stop button instead.",
                QSystemTrayIcon.MessageIcon.Warning,
                6000,
            )
        else:
            self.tray_icon.showMessage(
                "VoxScribe",
                f"Running in the background. Hold {GLOBAL_HOTKEY.upper()} anywhere to dictate.",
                QSystemTrayIcon.MessageIcon.Information,
                4000,
            )

    def _on_tray_activated(self, reason) -> None:  # noqa: ANN001
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._show_and_raise()

    def _show_and_raise(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event) -> None:  # noqa: N802, ANN001
        """Closing the window (the X button) minimizes to tray instead of
        quitting -- F9 and the floating indicator keep working in the
        background. Use the tray menu's "Quit" to actually exit."""
        if getattr(self, "tray_icon", None) is not None:
            event.ignore()
            self.hide()
        else:
            # No tray available on this system -- fall back to a real quit.
            self._quit_app()

    # -- updates ------------------------------------------------------

    def _start_update_check(self, *, manual: bool) -> None:
        if self._update_checker is not None and self._update_checker.isRunning():
            return
        self._update_checker = UpdateCheckThread()
        self._update_checker.found.connect(lambda info: self._on_update_found(info))
        self._update_checker.none_found.connect(lambda: self._on_update_none_found(manual))
        self._update_checker.failed.connect(lambda msg: self._on_update_check_failed(msg, manual))
        self._update_checker.start()

    def _on_update_found(self, info: UpdateInfo) -> None:
        self._pending_update_url = info.url
        if self.tray_icon is not None:
            self.tray_icon.showMessage(
                "VoxScribe update available",
                f"Version {info.version} is available (you're on {__version__}). "
                "Click this notification to open the download page.",
                QSystemTrayIcon.MessageIcon.Information,
                8000,
            )

    def _on_update_none_found(self, manual: bool) -> None:
        if manual and self.tray_icon is not None:
            self.tray_icon.showMessage(
                "VoxScribe",
                f"You're up to date (v{__version__}).",
                QSystemTrayIcon.MessageIcon.Information,
                4000,
            )

    def _on_update_check_failed(self, message: str, manual: bool) -> None:
        if manual and self.tray_icon is not None:
            self.tray_icon.showMessage(
                "VoxScribe",
                f"Couldn't check for updates: {message}",
                QSystemTrayIcon.MessageIcon.Warning,
                5000,
            )

    def _on_tray_message_clicked(self) -> None:
        if self._pending_update_url:
            webbrowser.open(self._pending_update_url)
            self._pending_update_url = None

    def _open_logs_folder(self) -> None:
        CRASH_LOG_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(str(CRASH_LOG_DIR))  # noqa: S606 -- Windows-only app

    def _quit_app(self) -> None:
        try:
            keyboard.unhook_all()
        except Exception:  # noqa: BLE001
            pass
        if getattr(self, "tray_icon", None) is not None:
            self.tray_icon.hide()
        self._indicator.close()
        QApplication.instance().quit()

    # -- status helpers -----------------------------------------------

    def _set_status(self, text: str, kind: str) -> None:
        color = STATUS_COLORS.get(kind, STATUS_COLORS["ready"])
        self.status_label.setText(text)
        self.status_label.setStyleSheet(STATUS_LABEL_STYLE.format(color=color))

    def _set_record_button_recording(self, is_recording: bool) -> None:
        """Flips the record button's `recording` dynamic property, which the
        QSS in MAIN_STYLESHEET uses to swap it from accent-violet (idle) to
        green (actively recording) -- a clear at-a-glance state cue on top
        of the button's own text change."""
        self.record_button.setProperty("recording", is_recording)
        self.record_button.style().unpolish(self.record_button)
        self.record_button.style().polish(self.record_button)

    def _update_save_button(self) -> None:
        has_text = bool(self.transcript_area.toPlainText().strip())
        self.save_button.setEnabled(has_text)
        self.copy_button.setEnabled(has_text)
        self.clear_button.setEnabled(has_text)

    # -- save to file -----------------------------------------------------

    def save_transcript(self) -> None:
        text = self.transcript_area.toPlainText()
        if not text.strip():
            return

        default_name = f"transcript_{datetime.now():%Y%m%d_%H%M%S}.txt"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Transcript", default_name, "Text Files (*.txt);;All Files (*)"
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        except OSError as exc:
            self._set_status(f"Save failed: {exc}", "error")
            return

        self._set_status(f"Saved to {path}", "ready")

    def copy_transcript(self) -> None:
        text = self.transcript_area.toPlainText()
        if not text.strip():
            return
        QApplication.clipboard().setText(text)
        self._set_status("Copied to clipboard", "ready")

    def clear_transcript(self) -> None:
        self.transcript_area.clear()
        self._set_status("Ready", "ready")

    # -- model loading --------------------------------------------------

    def _on_model_loaded(self, transcriber: Transcriber) -> None:
        self.transcriber = transcriber
        self._set_status("Ready", "ready")
        self.record_button.setEnabled(True)

    def _on_model_load_failed(self, message: str) -> None:
        self._set_status("Failed to load model", "error")
        self.transcript_area.append(f"[error] {message}")

    # -- recording / transcription --------------------------------------

    def toggle_recording(self) -> None:
        if self.stream is None:
            self._start_recording()
        else:
            self._stop_recording()

    # -- hold-to-talk hotkey handlers ------------------------------------

    def _handle_hotkey_press(self) -> None:
        if self._f9_key_down:
            # Key-repeat guard: holding a key down can fire repeated
            # "press" events on some systems -- ignore all but the first
            # until a release is seen.
            return
        self._f9_key_down = True
        # Guard against starting a new recording while the previous one is
        # still transcribing on a background TranscribeThread: the on-screen
        # button is disabled during that window (see _stop_recording), but
        # this global OS-level hotkey bypasses button state entirely. Without
        # this check, a quick second hold-and-release overwrites self._worker
        # while the first TranscribeThread is still running, and Qt fatally
        # errors ("QThread: Destroyed while thread is still running") once
        # the orphaned thread object is garbage collected.
        transcribing = self._worker is not None and self._worker.isRunning()
        if self.transcriber is None:
            # Model still loading on ModelLoaderThread. Recording itself
            # doesn't need it, but _stop_recording hands the buffer straight
            # to a TranscribeThread(self.transcriber, ...) -- with no guard
            # here that used to run with transcriber=None and surface a
            # confusing "'NoneType' object has no attribute 'transcribe'"
            # instead of telling the user what's actually happening.
            self._indicator.show_status("not_ready")
            QTimer.singleShot(1500, self._indicator.hide_indicator)
            return
        if self.stream is None and not transcribing:
            self._hotkey_active_session = True
            self._start_recording()

    def _handle_hotkey_release(self) -> None:
        self._f9_key_down = False
        if self._hotkey_active_session and self.stream is not None:
            self._hotkey_active_session = False
            self._stop_recording()

    def _start_recording(self) -> None:
        self._chunks = []
        device = _default_input_device()
        # Record at the device's own native rate rather than forcing 16kHz --
        # some devices/drivers (e.g. a laptop's internal mic falling back to
        # when a Bluetooth headset isn't connected) reject a forced 16kHz
        # request outright. Resample down to 16kHz for Whisper after capture.
        self._record_rate = device_native_samplerate(device)

        def callback(indata, frames, time_info, status):  # noqa: ANN001
            self._chunks.append(indata[:, 0].copy())

        try:
            self.stream = sd.InputStream(
                samplerate=self._record_rate,
                channels=1,
                dtype="float32",
                device=device,
                callback=callback,
            )
            self.stream.start()
        except Exception as exc:  # noqa: BLE001
            self.stream = None
            self._hotkey_active_session = False
            self._set_status(f"No microphone available: {exc}", "error")
            return
        self.record_button.setText("Stop Recording")
        self._set_record_button_recording(True)
        self._set_status("Recording...", "recording")
        self._indicator.show_status("recording")

    def _stop_recording(self) -> None:
        self.stream.stop()
        self.stream.close()
        self.stream = None

        self.record_button.setEnabled(False)
        self.record_button.setText("Start Recording")
        self._set_record_button_recording(False)
        self._set_status("Transcribing...", "transcribing")
        self._indicator.show_status("transcribing")

        audio = np.concatenate(self._chunks) if self._chunks else np.zeros(0, dtype=np.float32)
        audio = resample_to_16k(audio, self._record_rate)
        self._chunks = []

        self._worker = TranscribeThread(self.transcriber, audio)
        self._worker.done.connect(self._on_transcribed)
        self._worker.failed.connect(self._on_transcribe_failed)
        self._worker.start()

    def _on_transcribed(self, text: str) -> None:
        text = clean_transcript(text) if text else text
        self.transcript_area.append(text if text else "[no speech recognized]")
        self.record_button.setEnabled(True)
        self._indicator.hide_indicator()

        if text:
            # Simulate typing directly into whatever window currently has
            # focus (not necessarily this app -- that's the point of the
            # global hotkey). This deliberately does NOT touch the
            # clipboard, so it won't clobber anything the user has copied.
            QTimer.singleShot(150, lambda: self._type_into_focused_window(text))
            self._set_status("Typed into active window", "ready")
        else:
            self._set_status("Ready", "ready")

    def _type_into_focused_window(self, text: str) -> None:
        try:
            # A small per-character delay matters here: some target apps
            # (rich-text/JS-driven inputs, not plain native text fields --
            # e.g. a chat box in an Electron/web-based app) can't keep up
            # with instantly-injected keystrokes and end up scrambling the
            # character order. 12ms/char wasn't enough for some inputs
            # (reported: two overlapping copies of the same phrase
            # interleaved character-by-character) -- 30ms/char still reads
            # as instant to a human but gives slower inputs enough room.
            keyboard.write(text, delay=0.03)
        except Exception:  # noqa: BLE001
            pass

    def _on_transcribe_failed(self, message: str) -> None:
        self.transcript_area.append(f"[error] {message}")
        self._set_status("Ready", "ready")
        self.record_button.setEnabled(True)
        self._indicator.hide_indicator()
