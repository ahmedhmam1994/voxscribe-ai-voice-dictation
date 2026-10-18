"""Main window for the VoxScribe app.

Phase 4: real push-to-talk UI wired to the app's own core modules
(core/audio_capture.py, core/transcribe.py). Model loading happens on a
background QThread at startup, and each recording is transcribed on a
background QThread on Stop, so the UI never freezes. This follows the
pattern proven out in test_ptt_visual.py.
"""

from __future__ import annotations

import os
import threading
import time
import webbrowser
import winsound
from datetime import datetime
from pathlib import Path

import keyboard
import numpy as np
import sounddevice as sd
from PySide6.QtCore import (
    QByteArray,
    QEasingCurve,
    QObject,
    QPropertyAnimation,
    QSequentialAnimationGroup,
    QSize,
    Qt,
    QThread,
    QTimer,
    Signal,
)
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.floating_indicator import FloatingIndicator
from app.insights_page import InsightsPage
from app.motion import animate_progress, fade_in
from app.speed_test import SpeedTestDialog
from app.version import __version__
from app.welcome import WelcomeDialog
from app.whats_new import whats_new_text
from core import (
    app_profiles,
    batch,
    code_dictation,
    diarize,
    history,
    modes,
    network_guard,
    replacements,
    smart_format,
    snippets,
    templates,
    transcript_export,
    vocab_learner,
    word_lists,
)
from core import license as hotkey_license
from core import settings as hotkey_settings
from core.audio_capture import (
    SAMPLE_RATE,
    RollingBuffer,
    device_native_samplerate,
    list_input_devices,
    peak_levels,
    resample_to_16k,
    resolve_input_device,
)
from core.captions import review_flags, split_segments_timed
from core.chime import make_chime
from core.cleanup import clean_transcript
from core.crash_reporter import LOG_DIR as CRASH_LOG_DIR
from core.focused_window import focus_window, foreground_process_name, foreground_window_handle
from core.hold_gate import HoldGate
from core.password_field import focused_is_password
from core.redo import (
    CAREFUL_BEAM_SIZE,
    LATE_HINT_SEC,
    REDO_WINDOW_SEC,
    TYPED_HINT_COUNT,
    pick_redo_model,
)
from core.srt import format_srt, format_timestamp
from core.transcribe import (
    MODEL_APPROX_MB,
    Transcriber,
    is_model_downloaded,
    load_transcriber,
    model_cache_bytes,
)
from core.updater import UpdateCheckThread, UpdateDownloadThread, UpdateInfo
from core.voice_commands import (
    apply_replace,
    apply_trailing_replace,
    apply_transform,
    apply_voice_commands,
    compute_deletion,
    compute_rewrite,
    get_editing_command,
    get_replace_command,
    get_transform_command,
    is_send_command,
    split_trailing_send,
    split_trailing_transform,
)

ICON_PATH = Path(__file__).parent / "icon.ico"
UPDATE_CHECK_INTERVAL_MS = 7 * 24 * 60 * 60 * 1000  # weekly

# -- visual palette --------------------------------------------------------
# A cohesive dark theme (near-black surfaces, soft green accent) rather than
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
ACCENT = "#3ecf8e"
ACCENT_HOVER = "#4ee0a0"
ACCENT_PRESSED = "#269e69"
ACCENT_DISABLED = "#3a3b4c"


# -- real icons (Lucide, ISC-licensed SVGs bundled in app/icons/) ----------
# Previously hand-drawn with QPainter primitives; swapped for a real icon
# set since the hand-drawn shapes read as amateurish at actual UI size.
# Lucide's SVGs use stroke="currentColor" so they can be recolored per call
# (active/disabled/hover states, different theme colors) by substituting
# that token before rendering -- one bundled file per icon, no per-color
# duplicate assets needed.
_ICONS_DIR = Path(__file__).parent / "icons"
_svg_cache: dict[str, str] = {}


def _svg_source(name: str) -> str:
    if name not in _svg_cache:
        _svg_cache[name] = (_ICONS_DIR / f"{name}.svg").read_text(encoding="utf-8")
    return _svg_cache[name]


def _load_svg_icon(name: str, size: int, color: str) -> QIcon:
    svg = _svg_source(name).replace("currentColor", color)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def _icon_mic(size: int = 22, color: str = "#ffffff") -> QIcon:
    return _load_svg_icon("mic", size, color)


def _icon_stop(size: int = 22, color: str = "#ffffff") -> QIcon:
    return _load_svg_icon("square", size, color)


def _icon_save(size: int = 16, color: str = TEXT_PRIMARY) -> QIcon:
    return _load_svg_icon("download", size, color)


def _icon_copy(size: int = 16, color: str = TEXT_PRIMARY) -> QIcon:
    return _load_svg_icon("copy", size, color)


def _icon_clear(size: int = 16, color: str = TEXT_PRIMARY) -> QIcon:
    return _load_svg_icon("trash-2", size, color)


def _icon_settings(size: int = 18, color: str = TEXT_MUTED) -> QIcon:
    return _load_svg_icon("settings", size, color)


def _icon_globe(size: int = 13, color: str = TEXT_MUTED) -> QIcon:
    return _load_svg_icon("globe", size, color)


def _icon_keyboard(size: int = 14, color: str = TEXT_FAINT) -> QIcon:
    return _load_svg_icon("keyboard", size, color)


def _icon_insights(size: int = 18, color: str = TEXT_MUTED) -> QIcon:
    return _load_svg_icon("bar-chart-3", size, color)


def _icon_upload(size: int = 16, color: str = TEXT_PRIMARY) -> QIcon:
    return _load_svg_icon("upload", size, color)


class _StatusDot(QWidget):
    """Small solid-color circle used inside the status pill."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(9, 9)
        self._color = QColor(TEXT_MUTED)

    def set_color(self, hex_color: str) -> None:
        self._color = QColor(hex_color)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802, ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._color)
        painter.drawEllipse(self.rect())


class StatusPill(QWidget):
    """Replaces the old plain colored status text with a small badge (dot +
    label on a card surface) -- gives the app's current state actual visual
    weight instead of relying on text color alone to carry the meaning."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("statusPill")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 14, 6)
        layout.setSpacing(8)
        self._dot = _StatusDot(self)
        layout.addWidget(self._dot)
        self._label = QLabel("Loading model...")
        self._label.setObjectName("statusPillLabel")
        layout.addWidget(self._label)

    def set_status(self, text: str, kind: str) -> None:
        color = STATUS_COLORS.get(kind, STATUS_COLORS["ready"])
        self._dot.set_color(color)
        self._label.setText(text)
        self._label.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: 600;")

    def text(self) -> str:
        return self._label.text()


class HotkeyBridge(QObject):
    """Relays the global hotkey (fired on a non-Qt background thread by the
    `keyboard` library) into the Qt event loop via signals. Qt auto-queues
    signal emissions across threads to the receiver's own thread, so this is
    the safe way to trigger GUI/audio code from the hotkey callback.

    Press/release are separate signals (rather than one toggle signal)
    because the global hotkey is now hold-to-talk: holding it down starts
    recording, releasing it stops and transcribes."""

    press_requested = Signal()
    release_requested = Signal()
    # The Pro second-language key.
    alt_press_requested = Signal()
    alt_release_requested = Signal()
    # The Try harder key (core/redo.py).
    redo_requested = Signal()
    redo_too_late = Signal()

STATUS_COLORS = {
    "loading": TEXT_MUTED,
    "ready": TEXT_MUTED,
    "recording": "#3ecf8e",  # green
    "transcribing": "#f0a54a",  # amber
    "error": "#f0546b",  # red
}

MAIN_STYLESHEET = f"""
QMainWindow, QWidget#centralWidget {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #14151d, stop:1 #0e0f14);
}}

QWidget {{
    font-family: "Segoe UI";
    font-size: 13px;
    color: {TEXT_PRIMARY};
}}

QCheckBox {{
    color: {TEXT_MUTED};
    font-size: 12px;
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {BORDER};
    background: {BG_CARD};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
}}

QWidget#statusPill {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1f212c, stop:1 #1a1c26);
    border: 1px solid {BORDER_SOFT};
    border-radius: 15px;
}}
QLabel#statusPillLabel {{
    font-size: 13px;
    font-weight: 600;
}}

QLabel#transcriptCaption {{
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.6px;
    color: {TEXT_MUTED};
}}

QLabel#hotkeyHint {{
    font-size: 11px;
    color: {TEXT_FAINT};
}}
QLabel#hotkeyHintError {{
    font-size: 11px;
    color: #f0546b;
}}
QLabel#keyBadge {{
    font-size: 11px;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 1px 6px;
}}

QPushButton#recordButton {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #34b57a, stop:1 #1f8f5c);
    color: #ffffff;
    font-size: 15px;
    font-weight: 700;
    border: none;
    border-radius: 12px;
    padding: 10px 16px;
}}
QPushButton#recordButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4ee0a0, stop:1 #2bb673);
}}
QPushButton#recordButton:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2bb673, stop:1 #17754d);
}}
QPushButton#recordButton:disabled {{
    background: {ACCENT_DISABLED};
    color: {TEXT_FAINT};
}}
QPushButton#recordButton[recording="true"] {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3ecf8e, stop:1 #269e69);
}}
QPushButton#recordButton[recording="true"]:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4ee0a0, stop:1 #34b57a);
}}

QPushButton#secondaryButton {{
    background: {BG_CARD};
    color: {TEXT_PRIMARY};
    font-size: 13px;
    font-weight: 600;
    border: 1px solid {BORDER};
    border-radius: 12px;
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

QPushButton#languageBadge {{
    background: {BG_CARD};
    color: {TEXT_MUTED};
    font-size: 12px;
    font-weight: 600;
    border: 1px solid {BORDER};
    border-radius: 15px;
    padding: 5px 12px 5px 10px;
}}
QPushButton#languageBadge:hover {{
    background: {BG_CARD_HOVER};
    border: 1px solid {ACCENT};
    color: {TEXT_PRIMARY};
}}

QPushButton#iconOnlyButton {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 17px;
}}
QPushButton#iconOnlyButton:hover {{
    background: {BG_CARD_HOVER};
    border: 1px solid {ACCENT};
}}
QPushButton#iconOnlyButton:pressed {{
    background: {BORDER};
}}

QPushButton#primaryOutlineButton {{
    background: transparent;
    color: {ACCENT};
    font-size: 13px;
    font-weight: 700;
    border: 1px solid {ACCENT};
    border-radius: 12px;
    padding: 8px 14px;
}}
QPushButton#primaryOutlineButton:hover {{
    background: rgba(62, 207, 142, 0.14);
}}
QPushButton#primaryOutlineButton:pressed {{
    background: rgba(62, 207, 142, 0.24);
}}
QPushButton#primaryOutlineButton:disabled {{
    color: {TEXT_FAINT};
    border: 1px solid {BORDER_SOFT};
}}

QPushButton#ghostButton {{
    background: transparent;
    color: {TEXT_MUTED};
    font-size: 13px;
    font-weight: 600;
    border: 1px solid transparent;
    border-radius: 12px;
    padding: 8px 14px;
}}
QPushButton#ghostButton:hover {{
    color: #f0546b;
    background: rgba(240, 84, 107, 0.10);
    border: 1px solid rgba(240, 84, 107, 0.35);
}}
QPushButton#ghostButton:pressed {{
    background: rgba(240, 84, 107, 0.18);
}}
QPushButton#ghostButton:disabled {{
    color: {TEXT_FAINT};
    background: transparent;
    border: 1px solid transparent;
}}

QTextEdit#transcriptArea {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1d1f2a, stop:1 #181a23);
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 12px;
    font-size: 14px;
    line-height: 1.4;
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
}}
QTextEdit#transcriptArea[hasContent="false"] {{
    border: 1px solid {BORDER_SOFT};
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

QWidget#accentStrip {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #1f8f5c, stop:0.5 {ACCENT}, stop:1 #8eeab0);
}}

QWidget#sidebar {{
    background: {BG_WINDOW};
    border-right: 1px solid {BORDER_SOFT};
}}
QLabel#wordmark {{
    color: {TEXT_PRIMARY};
    font-size: 16px;
    font-weight: 700;
    padding-left: 6px;
}}
QPushButton#sidebarNavButton {{
    background: transparent;
    color: {TEXT_MUTED};
    text-align: left;
    font-size: 13px;
    font-weight: 600;
    border: none;
    border-radius: 9px;
    padding: 8px 10px;
}}
QPushButton#sidebarNavButton:hover {{
    background: {BG_CARD};
    color: {TEXT_PRIMARY};
}}
QPushButton#sidebarNavButton:checked {{
    background: rgba(62, 207, 142, 0.16);
    color: {TEXT_PRIMARY};
}}

QWidget#heroBanner {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #163a28, stop:0.55 #2f7a52, stop:1 #4aa06c);
    border-radius: 14px;
}}
QLabel#heroTitle {{
    color: #ffffff;
    font-size: 17px;
    font-weight: 700;
}}
QLabel#heroSubtitle {{
    color: rgba(255, 255, 255, 0.78);
    font-size: 12px;
}}

QScrollArea#historyScroll {{
    background: transparent;
    border: none;
}}
QScrollArea#historyScroll QWidget {{
    background: transparent;
}}
QWidget#historyItem {{
    background: transparent;
    border-radius: 8px;
}}
QWidget#historyItem:hover {{
    background: {BG_CARD};
}}
QLabel#historyTime {{
    color: {TEXT_FAINT};
    font-size: 11px;
}}
QLabel#historyText {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}
QLabel#historyEmpty {{
    color: {TEXT_FAINT};
    font-size: 12px;
    padding: 8px;
}}

QLabel#pageTitle {{
    color: {TEXT_PRIMARY};
    font-size: 20px;
    font-weight: 700;
}}
QWidget#statCard {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1f212c, stop:1 #1a1c26);
    border: 1px solid {BORDER_SOFT};
    border-radius: 14px;
}}
QLabel#statCardValue {{
    color: {TEXT_PRIMARY};
    font-size: 26px;
    font-weight: 700;
}}
QLabel#statCardLabel {{
    color: {TEXT_MUTED};
    font-size: 12px;
    font-weight: 600;
}}
"""

SETTINGS_DIALOG_STYLESHEET = f"""
QDialog, QWidget#settingsPage {{
    background: {BG_WINDOW};
}}
QWidget#settingsNav {{
    background: {BG_WINDOW};
    border-right: 1px solid {BORDER_SOFT};
}}
QLabel#settingsPageTitle {{
    color: {TEXT_PRIMARY};
    font-size: 20px;
    font-weight: 700;
}}
QLabel#settingsPageSubtitle {{
    color: {TEXT_FAINT};
    font-size: 12px;
}}
QLabel {{
    color: {TEXT_PRIMARY};
    font-size: 13px;
}}
QLabel#settingsSectionLabel {{
    color: {TEXT_MUTED};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.4px;
}}
QComboBox {{
    background: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 10px;
}}
QComboBox:hover {{
    border: 1px solid {ACCENT};
}}
QComboBox QAbstractItemView {{
    background: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    outline: none;
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
}}
QCheckBox {{
    color: {TEXT_PRIMARY};
    font-size: 13px;
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {BORDER};
    background: {BG_CARD};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
}}
QLineEdit {{
    background: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 10px;
    font-size: 13px;
}}
QLineEdit:focus {{
    border: 1px solid {ACCENT};
}}
QSpinBox {{
    background: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 13px;
}}
QSpinBox:focus {{
    border: 1px solid {ACCENT};
}}
QSpinBox::up-button, QSpinBox::down-button {{
    width: 0px;
    border: none;
}}
QTextEdit {{
    background: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 10px;
    font-size: 13px;
}}
QTextEdit:focus {{
    border: 1px solid {ACCENT};
}}
QLabel#settingsHint {{
    color: {TEXT_FAINT};
    font-size: 11px;
}}
QProgressBar#micLevelMeter {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    height: 10px;
    text-align: center;
}}
QProgressBar#micLevelMeter::chunk {{
    background: {ACCENT};
    border-radius: 6px;
}}
QProgressBar#micLevelMeter[clipping="true"]::chunk {{
    background: #f0546b;
}}
QDialogButtonBox QPushButton {{
    background: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 16px;
    min-width: 70px;
}}
QDialogButtonBox QPushButton:hover {{
    background: {BG_CARD_HOVER};
    border: 1px solid {ACCENT};
}}
QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollArea > QWidget > QWidget {{
    background: transparent;
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

TRAY_MENU_STYLESHEET = f"""
QMenu {{
    background: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px;
}}
QMenu::item {{
    padding: 7px 24px 7px 12px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background: {ACCENT};
    color: #ffffff;
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 6px 4px;
}}
"""


def _play_chime(kind: str) -> None:
    """Plays the soft start/stop chime (core/chime.py) on a short-lived
    background thread so a sound cue (Settings -> Play a sound) can't block
    the Qt event loop -- playing from memory is a blocking call. Best-effort:
    some systems/sandboxes have no audio device, so failures are swallowed
    rather than surfaced as an error over a cosmetic feature."""
    def _play() -> None:
        try:
            winsound.PlaySound(make_chime(kind), winsound.SND_MEMORY)
        except (OSError, RuntimeError):
            pass

    threading.Thread(target=_play, daemon=True).start()


def _play_start_sound() -> None:
    if hotkey_settings.get_sound_enabled():
        _play_chime("start")


def _play_stop_sound() -> None:
    if hotkey_settings.get_sound_enabled():
        _play_chime("stop")


class _NoWheelComboBox(QComboBox):
    """A dropdown that ignores the mouse wheel. Inside the scrolling
    Settings page, scrolling past a dropdown otherwise changes its value
    (hotkey, language, model size) instead of scrolling the page. Clicking
    the box and the arrow keys still work, and the open list scrolls
    normally."""

    def wheelEvent(self, event) -> None:  # noqa: N802, ANN001
        event.ignore()


class _NoWheelSpinBox(QSpinBox):
    """Same reason as _NoWheelComboBox: scrolling the Settings page must not
    change a number box it happens to pass over."""

    def wheelEvent(self, event) -> None:  # noqa: N802, ANN001
        event.ignore()


class ModelLoaderThread(QThread):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(str)
    # Megabytes downloaded so far and the expected total, for the progress bar.
    download = Signal(int, int)

    def _watch_download(self, model_size: str, stop: threading.Event) -> None:
        """Reports first-run download progress by watching the cache folder
        grow -- the download itself runs inside faster-whisper, which gives
        no progress callback."""
        expected_mb = MODEL_APPROX_MB.get(model_size)
        if not expected_mb:
            return
        last_mb = -1
        while not stop.wait(1.0):
            mb = model_cache_bytes(model_size) // (1024 * 1024)
            if 0 < mb < expected_mb * 0.97 and mb != last_mb:
                last_mb = mb
                self.progress.emit(f"Downloading model... {mb} of about {expected_mb} MB")
                self.download.emit(mb, expected_mb)

    def run(self) -> None:
        stop = threading.Event()
        try:
            # Settings -> Whisper Model Size: takes effect on the next
            # launch (this thread only runs at startup), not live mid-
            # session -- switching sizes may need to download a different
            # model file, which shouldn't happen silently while the app is
            # already running.
            model_size = hotkey_settings.get_model_size()
            if model_size in hotkey_settings.PRO_MODEL_SIZES and not hotkey_license.is_pro():
                # Defense-in-depth: the Settings UI already disables these
                # entries when not Pro, but a size could still be sitting
                # in QSettings from when a license was active (e.g. it was
                # since removed) -- fall back rather than loading a model
                # the user isn't licensed for.
                model_size = hotkey_settings.DEFAULT_MODEL_SIZE
            threading.Thread(
                target=self._watch_download, args=(model_size, stop), daemon=True
            ).start()
            transcriber = load_transcriber(model_size)
        except Exception as exc:  # noqa: BLE001
            stop.set()
            self.failed.emit(str(exc))
            return
        stop.set()
        self.done.emit(transcriber)


class MicTestThread(QThread):
    """Streams live peak-amplitude levels from a mic for the Settings
    "Test microphone" calibration check. Runs peak_levels() on a background
    thread so the level meter can update without blocking the dialog's UI
    thread, and stops cleanly via stop() rather than being killed."""

    level = Signal(float)
    failed = Signal(str)

    def __init__(self, device: int | None) -> None:
        super().__init__()
        self.device = device
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        try:
            for peak in peak_levels(self.device):
                if self._stop:
                    return
                self.level.emit(peak)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class TranscribeThread(QThread):
    done = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        transcriber: Transcriber,
        audio: np.ndarray,
        language: str | None = "en",
        initial_prompt: str | None = None,
        task: str = "transcribe",
        beam_size: int = 1,
        load_size: str | None = None,
    ) -> None:
        super().__init__()
        self.transcriber = transcriber
        self.audio = audio
        self.language = language
        self.initial_prompt = initial_prompt
        self.task = task
        self.beam_size = beam_size
        # Try harder: load this (already downloaded) model first, offline.
        # The loaded model is handed back on `loaded` so it can be reused.
        self.load_size = load_size

    loaded = Signal(object)

    def run(self) -> None:
        try:
            if self.load_size is not None:
                self.transcriber = Transcriber(self.load_size, local_files_only=True)
                self.loaded.emit(self.transcriber)
            text = self.transcriber.transcribe(
                self.audio,
                language=self.language,
                initial_prompt=self.initial_prompt,
                task=self.task,
                beam_size=self.beam_size,
            )
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.done.emit(text)


class FileTranscribeThread(QThread):
    """Same shape as TranscribeThread, but for an existing file on disk
    (see Transcriber.transcribe_file) rather than a captured mic buffer."""

    done = Signal(str)
    failed = Signal(str)
    status = Signal(str)
    progress = Signal(int)
    cancelled = Signal()

    def __init__(
        self,
        transcriber: Transcriber,
        path: str,
        language: str | None = "en",
        initial_prompt: str | None = None,
        task: str = "transcribe",
        export_srt: bool = False,
        export_extras: bool = False,
        label_speakers: bool = False,
        speaker_count: int = 0,
        speaker_names: list[str] | None = None,
        caption_line_chars: int = 0,
    ) -> None:
        super().__init__()
        self.transcriber = transcriber
        self.path = path
        self.language = language
        self.initial_prompt = initial_prompt
        self.task = task
        self.export_srt = export_srt
        self.export_extras = export_extras
        self.label_speakers = label_speakers
        self.speaker_count = speaker_count
        self.speaker_names = speaker_names or []
        self.caption_line_chars = caption_line_chars
        self.speaker_error: str | None = None
        self._run_gate = threading.Event()
        self._run_gate.set()
        self._stop_requested = False
        self.review_total = 0
        self.review_notes: list[str] = []
        self.srt_path: str | None = None
        self.extra_paths: list[str] = []

    def set_paused(self, paused: bool) -> None:
        if paused:
            self._run_gate.clear()
        else:
            self._run_gate.set()

    def request_stop(self) -> None:
        self._stop_requested = True
        self._run_gate.set()

    def _control(self) -> bool:
        """Blocks while paused; True once a stop was asked for."""
        self._run_gate.wait()
        return self._stop_requested

    def run(self) -> None:
        try:
            detailed = self.transcriber.transcribe_file_detailed(
                self.path,
                language=self.language,
                initial_prompt=self.initial_prompt,
                task=self.task,
                on_progress=lambda pct: self.progress.emit(int(pct)),
                control=self._control,
            )
        except InterruptedError:
            self.cancelled.emit()
            return
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return

        segments = [(start, end, text) for start, end, text, _words in detailed]
        if self.label_speakers:
            labeled = self._label_speakers(segments)
            if len(labeled) == len(detailed):
                # Labelled text no longer matches the words, so those segments
                # fall back to the even split inside split_segments_timed.
                detailed = [
                    (start, end, text, old[3])
                    for (start, end, text), old in zip(labeled, detailed, strict=True)
                ]
            segments = labeled

        cards = split_segments_timed(detailed, self.caption_line_chars)
        if self.export_srt or self.export_extras:
            # Flags only: nothing is changed, the user decides.
            flags = review_flags(cards)
            self.review_total = len(flags)
            self.review_notes = [
                f"card {number} at {format_timestamp(cards[number - 1][0])[:8]}: {reason}"
                for number, reason in flags[:5]
            ]

        # Never replace a file that is already there (it may be a hand
        # corrected caption): save under "name (2)" instead.
        wanted = ([".srt"] if self.export_srt else []) + (
            [".vtt", ".md", ".docx"] if self.export_extras else []
        )
        out_base = batch.unused_base(self.path, wanted) if wanted else None

        if self.export_srt:
            srt_path = str(out_base.with_name(out_base.name + ".srt"))
            try:
                with open(srt_path, "w", encoding="utf-8") as f:
                    f.write(format_srt(cards))
                self.srt_path = srt_path
            except OSError:
                # Transcription itself succeeded -- still hand the text back
                # rather than failing the whole import over a write error.
                pass

        if self.export_extras:
            self._write_extras(segments, cards, out_base)

        text = " ".join(text.strip() for _start, _end, text in segments).strip()
        self.done.emit(text)

    def _label_speakers(
        self, segments: list[tuple[float, float, str]]
    ) -> list[tuple[float, float, str]]:
        """Pro: prefixes each segment with who said it. On any failure the
        transcript is kept as is and the reason is stored in speaker_error."""
        try:
            if not diarize.models_ready():
                diarize.download_models(self.status.emit)
            from faster_whisper.audio import decode_audio

            self.status.emit("Finding speakers...")
            audio = decode_audio(self.path, sampling_rate=diarize.SAMPLE_RATE)
            turns = diarize.diarize(audio, self.speaker_count)
        except Exception as exc:  # noqa: BLE001
            self.speaker_error = str(exc)
            return segments
        return diarize.label_segments(segments, turns, self.speaker_names)

    def _write_extras(
        self,
        segments: list[tuple[float, float, str]],
        cards: list[tuple[float, float, str]],
        base: Path,
    ) -> None:
        """Pro: WebVTT, Markdown and Word copies next to the file."""
        title = Path(self.path).stem

        def named(suffix: str) -> Path:
            return base.with_name(base.name + suffix)

        outputs = {
            named(".vtt"): transcript_export.format_vtt(cards).encode("utf-8"),
            named(".md"): transcript_export.format_markdown(segments, title).encode("utf-8"),
            named(".docx"): transcript_export.format_docx(segments, title),
        }
        for path, data in outputs.items():
            try:
                path.write_bytes(data)
                self.extra_paths.append(str(path))
            except OSError:
                continue


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("VoxScribe")
        screen = QApplication.primaryScreen()
        tall = screen.availableGeometry().height() - 40 if screen else 820
        self.resize(1120, max(740, min(900, tall)))
        self.setMinimumSize(960, 740)
        self.setStyleSheet(MAIN_STYLESHEET)
        if ICON_PATH.exists():
            icon = QIcon(str(ICON_PATH))
            self.setWindowIcon(icon)
            QApplication.instance().setWindowIcon(icon)

        self.transcriber: Transcriber | None = None
        self.stream: sd.InputStream | None = None
        self._chunks: list[np.ndarray] = []
        self._record_rate: int = SAMPLE_RATE
        self._last_recording_duration: float = 0.0
        # The window the user was dictating into, captured when recording
        # stops -- transcription runs in the background and finishes after a
        # delay, long enough for the user to have switched windows in the
        # meantime, which would otherwise send the typed text to whatever
        # they switched to instead of what they meant to dictate into.
        self._recording_target_hwnd: int | None = None
        # Tracks the last text VoxScribe itself typed and which window it
        # went into, so a spoken "scratch that" / "delete last word" /
        # "delete last sentence" can Backspace some or all of it back out --
        # but only into the same window, never a different one the user has
        # since switched to. See core/voice_commands.py's get_editing_command().
        self._last_typed_text: str = ""
        self._last_typed_hwnd: int | None = None
        self._loader: ModelLoaderThread | None = None
        self._worker: TranscribeThread | None = None
        self._file_worker: FileTranscribeThread | None = None
        self._retired_file_workers: list[FileTranscribeThread] = []
        self._balloon_action = None
        self._held_text: str | None = None
        self._import_queue: list[str] = []
        self._batch: dict | None = None
        self.setAcceptDrops(True)

        # Hold-to-talk state for the global hotkey (configurable -- see
        # core/settings.py -- F9 by default):
        # - _hotkey_key_down tracks the *physical* key state so repeated
        #   "press" events fired by key-repeat (common while holding a key
        #   down, depending on OS/driver) don't re-trigger start_recording.
        # - _hotkey_active_session tracks whether the *current* recording
        #   was started by the hotkey (vs. the on-screen button), so
        #   releasing the hotkey only stops a recording it actually started.
        self._hotkey = hotkey_settings.get_hotkey()
        self._hotkey_key_down = False
        self._hotkey_active_session = False
        self._template_session: templates.TemplateSession | None = None
        self._template_last_turn = 0.0
        # (language,) while the Pro second-language key is dictating; None otherwise.
        self._language_override: tuple[str | None] | None = None
        # The focused program's Pro profile, read when a recording starts.
        self._recording_profile: dict[str, object] = {}
        self._hold_gate: HoldGate | None = None
        self._hold_other_hook = None

        # Optional "keep microphone ready" mode: one mic stream stays open
        # and feeds a short in-memory rolling buffer, so a recording starts
        # with the last ~0.5s already captured. See RollingBuffer.
        self._ready_stream: sd.InputStream | None = None
        self._ready_buffer: RollingBuffer | None = None
        self._ready_rate: int = SAMPLE_RATE
        self._ready_device: int | None = None
        self._capturing = False

        # Small floating "recording/transcribing" pill -- see
        # app/floating_indicator.py. Hidden except while active.
        self._indicator = FloatingIndicator()

        # Don't quit the whole app just because MainWindow is hidden (tray
        # behavior); closeEvent() below hides rather than closes it anyway,
        # but this is a belt-and-suspenders safeguard.
        QApplication.instance().setQuitOnLastWindowClosed(False)

        central = QWidget(self)
        central.setObjectName("centralWidget")
        outer_layout = QVBoxLayout(central)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        accent_strip = QWidget()
        accent_strip.setObjectName("accentStrip")
        accent_strip.setFixedHeight(3)
        outer_layout.addWidget(accent_strip)

        body_row = QHBoxLayout()
        body_row.setContentsMargins(0, 0, 0, 0)
        body_row.setSpacing(0)
        outer_layout.addLayout(body_row, stretch=1)

        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(184)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 20, 12, 20)
        sidebar_layout.setSpacing(4)

        wordmark = QLabel("VoxScribe")
        wordmark.setObjectName("wordmark")
        sidebar_layout.addWidget(wordmark)
        sidebar_layout.addSpacing(20)

        self._pages = QStackedWidget()

        self._nav_buttons: dict[int, QPushButton] = {}

        def _add_nav(label: str, icon: QIcon, page_index: int) -> None:
            btn = QPushButton(f"  {label}")
            btn.setObjectName("sidebarNavButton")
            btn.setIcon(icon)
            btn.setIconSize(QSize(17, 17))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setCheckable(True)
            btn.setMinimumHeight(38)
            btn.clicked.connect(lambda: self._switch_page(page_index))
            sidebar_layout.addWidget(btn)
            self._nav_buttons[page_index] = btn

        _add_nav("Dictation", _icon_mic(17, TEXT_MUTED), 0)
        _add_nav("Insights", _icon_insights(17, TEXT_MUTED), 1)

        sidebar_layout.addStretch(1)

        settings_nav_button = QPushButton("  Settings")
        settings_nav_button.setObjectName("sidebarNavButton")
        settings_nav_button.setIcon(_icon_settings(17, TEXT_MUTED))
        settings_nav_button.setIconSize(QSize(17, 17))
        settings_nav_button.setCursor(Qt.PointingHandCursor)
        settings_nav_button.setMinimumHeight(38)
        settings_nav_button.setCheckable(True)
        settings_nav_button.clicked.connect(self._open_settings_dialog)
        sidebar_layout.addWidget(settings_nav_button)
        self._settings_nav_button = settings_nav_button
        self._settings_close = None

        body_row.addWidget(sidebar)
        body_row.addWidget(self._pages, stretch=1)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(36, 26, 36, 22)
        layout.setSpacing(14)
        # Scrolls instead of overlapping when the window is shorter than the page.
        page_scroll = QScrollArea()
        page_scroll.setWidgetResizable(True)
        page_scroll.setFrameShape(QScrollArea.NoFrame)
        page_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        page_scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        page_scroll.setWidget(content)
        self._pages.addWidget(page_scroll)

        hero = QWidget()
        hero.setObjectName("heroBanner")
        hero.setFixedHeight(84)
        hero_row = QHBoxLayout(hero)
        hero_row.setContentsMargins(24, 10, 18, 10)
        hero_row.setSpacing(12)
        hero_text = QVBoxLayout()
        hero_text.setSpacing(2)
        hero_text.addStretch(1)
        hero_title = QLabel("Hold to talk, anywhere")
        hero_title.setObjectName("heroTitle")
        hero_text.addWidget(hero_title)
        hero_subtitle = QLabel(
            "Speak, release, and it's typed straight into whatever you're focused on."
        )
        hero_subtitle.setObjectName("heroSubtitle")
        hero_text.addWidget(hero_subtitle)
        hero_text.addStretch(1)
        hero_row.addLayout(hero_text, stretch=1)

        layout.addWidget(hero)

        status_row = QHBoxLayout()
        self.status_pill = StatusPill()
        status_row.addWidget(self.status_pill)
        # First-run model download: a bar that glides along next to the
        # status text, so a slow download reads as moving, not frozen.
        self._model_progress = QProgressBar()
        self._model_progress.setRange(0, 100)
        self._model_progress.setTextVisible(False)
        self._model_progress.setFixedSize(140, 6)
        self._model_progress.setStyleSheet(
            f"QProgressBar {{ background: {BG_CARD}; border: 1px solid {BORDER};"
            " border-radius: 3px; }"
            f"QProgressBar::chunk {{ background: {ACCENT}; border-radius: 2px; }}"
        )
        self._model_progress.hide()
        status_row.addWidget(self._model_progress)
        status_row.addStretch(1)

        self.language_badge = QPushButton()
        self.language_badge.setObjectName("languageBadge")
        self.language_badge.setIcon(_icon_globe(13, TEXT_MUTED))
        self.language_badge.setIconSize(QSize(13, 13))
        self.language_badge.setCursor(Qt.PointingHandCursor)
        self.language_badge.setToolTip("Dictation language -- click to change")
        self.language_badge.clicked.connect(self._open_settings_dialog)
        self._refresh_language_badge()
        status_row.addWidget(self.language_badge)
        layout.addLayout(status_row)

        # Icons drawn once and reused (see _icon_* helpers above) rather
        # than regenerated per state change.
        self._mic_icon = _icon_mic(22, "#ffffff")
        self._stop_icon = _icon_stop(22, "#ffffff")

        self.record_button = QPushButton("Start Recording")
        self.record_button.setObjectName("recordButton")
        self.record_button.setProperty("recording", False)
        self.record_button.setEnabled(False)
        self.record_button.setMinimumHeight(56)
        self.record_button.setMaximumHeight(56)
        self.record_button.setCursor(Qt.PointingHandCursor)
        self.record_button.setIcon(self._mic_icon)
        self.record_button.setIconSize(QSize(20, 20))
        self.record_button.clicked.connect(self.toggle_recording)
        record_row = QHBoxLayout()
        record_row.setSpacing(12)
        record_row.addWidget(self.record_button, stretch=1)
        layout.addLayout(record_row)

        # Soft glow beneath the record button -- violet at rest, shifting to
        # green and pulsing while actively recording -- so the primary
        # action reads as elevated/"live" rather than a flat rectangle.
        self._record_shadow = QGraphicsDropShadowEffect(self.record_button)
        self._record_shadow.setOffset(0, 6)
        self._record_shadow.setBlurRadius(24)
        self._record_shadow.setColor(QColor(62, 207, 142, 110))
        self.record_button.setGraphicsEffect(self._record_shadow)

        grow = QPropertyAnimation(self._record_shadow, b"blurRadius", self)
        grow.setDuration(700)
        grow.setStartValue(22)
        grow.setEndValue(42)
        grow.setEasingCurve(QEasingCurve.InOutSine)
        shrink = QPropertyAnimation(self._record_shadow, b"blurRadius", self)
        shrink.setDuration(700)
        shrink.setStartValue(42)
        shrink.setEndValue(22)
        shrink.setEasingCurve(QEasingCurve.InOutSine)
        self._record_pulse = QSequentialAnimationGroup(self)
        self._record_pulse.addAnimation(grow)
        self._record_pulse.addAnimation(shrink)
        self._record_pulse.setLoopCount(-1)

        # Hotkey hint row: icon + "Hold [KEY] anywhere..." with the key
        # itself rendered as a small badge, so the hold-to-talk hotkey (the
        # app's primary interaction) is more visible than plain muted text.
        hint_row = QHBoxLayout()
        hint_row.setSpacing(6)
        hint_row.setContentsMargins(4, 0, 0, 0)

        self._hotkey_hint_icon = QLabel()
        self._hotkey_hint_icon.setPixmap(_icon_keyboard(14, TEXT_FAINT).pixmap(14, 14))
        hint_row.addWidget(self._hotkey_hint_icon)

        self._hotkey_hint_prefix = QLabel("Hold")
        self._hotkey_hint_prefix.setObjectName("hotkeyHint")
        hint_row.addWidget(self._hotkey_hint_prefix)

        self._hotkey_badge = QLabel()
        self._hotkey_badge.setObjectName("keyBadge")
        hint_row.addWidget(self._hotkey_badge)

        self._hotkey_hint_suffix = QLabel()
        self._hotkey_hint_suffix.setObjectName("hotkeyHint")
        self._hotkey_hint_suffix.setWordWrap(True)
        hint_row.addWidget(self._hotkey_hint_suffix, stretch=1)


        layout.addLayout(hint_row)

        layout.addSpacing(6)

        button_row = record_row
        self.import_button = QPushButton("Import Audio")
        self.import_button.setObjectName("secondaryButton")
        self.import_button.setEnabled(False)
        self.import_button.setFixedSize(150, 56)
        self.import_button.setCursor(Qt.PointingHandCursor)
        self.import_button.setIcon(_icon_upload(16, TEXT_PRIMARY))
        self.import_button.setIconSize(QSize(15, 15))
        self.import_button.setToolTip(
            "Transcribe an audio or video file. You can also drop files here."
        )
        self.import_button.clicked.connect(self.import_audio_file)
        button_row.addWidget(self.import_button)

        self.import_folder_button = QPushButton("Import Folder")
        self.import_folder_button.setObjectName("secondaryButton")
        self.import_folder_button.setEnabled(False)
        self.import_folder_button.setFixedSize(150, 56)
        self.import_folder_button.setCursor(Qt.PointingHandCursor)
        self.import_folder_button.setToolTip(
            "Transcribe every audio and video file in a folder (Pro, 2 free runs)"
        )
        self.import_folder_button.clicked.connect(self.import_folder)
        button_row.addWidget(self.import_folder_button)

        options_row = QHBoxLayout()
        options_row.setSpacing(24)
        self.export_srt_checkbox = QCheckBox("Save .srt captions")
        self.export_srt_checkbox.setObjectName("exportSrtCheckbox")
        self.export_srt_checkbox.setToolTip(
            "Also save an .srt caption file next to each imported file"
        )
        options_row.addWidget(self.export_srt_checkbox)

        self.export_extras_checkbox = QCheckBox("Also .vtt, .md, .docx (Pro)")
        self.export_extras_checkbox.setObjectName("exportSrtCheckbox")
        self.export_extras_checkbox.setToolTip(
            "Also save .vtt, .md and Word (.docx) copies of each imported file (Pro)"
        )
        options_row.addWidget(self.export_extras_checkbox)

        self.label_speakers_checkbox = QCheckBox("Label speakers (Pro)")
        self.label_speakers_checkbox.setObjectName("exportSrtCheckbox")
        self.label_speakers_checkbox.setToolTip(
            "Label who is speaking in saved files "
            f"(Pro, downloads {diarize.APPROX_DOWNLOAD_MB} MB once)"
        )
        options_row.addWidget(self.label_speakers_checkbox)
        options_row.addStretch(1)
        layout.addLayout(options_row)

        self._batch_bar = QWidget()
        batch_layout = QHBoxLayout(self._batch_bar)
        batch_layout.setContentsMargins(0, 0, 0, 0)
        batch_layout.setSpacing(10)
        self._batch_label = QLabel("")
        self._batch_label.setWordWrap(True)
        batch_layout.addWidget(self._batch_label, stretch=1)
        self._batch_progress = QProgressBar()
        self._batch_progress.setRange(0, 100)
        self._batch_progress.setTextVisible(False)
        self._batch_progress.setFixedSize(150, 8)
        self._batch_progress.setStyleSheet(
            f"QProgressBar {{ background: {BG_CARD}; border: 1px solid {BORDER};"
            " border-radius: 4px; }"
            f"QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}"
        )
        batch_layout.addWidget(self._batch_progress)

        def _batch_button(text: str, name: str, handler) -> QPushButton:  # noqa: ANN001
            button = QPushButton(text)
            button.setObjectName(name)
            button.setCursor(Qt.PointingHandCursor)
            button.setFixedHeight(30)
            button.setStyleSheet("padding: 3px 14px;")
            button.clicked.connect(handler)
            batch_layout.addWidget(button)
            return button

        self._batch_pause_button = _batch_button(
            "Pause", "secondaryButton", self._toggle_import_pause
        )
        self._batch_cancel_button = _batch_button("Cancel", "ghostButton", self._cancel_import)
        self._batch_retry_button = _batch_button("Retry", "secondaryButton", self._retry_batch)
        self._batch_open_button = _batch_button(
            "Open folder", "primaryOutlineButton", self._open_batch_folder
        )
        self._batch_bar.hide()
        self._batch_retry_button.hide()
        self._retry_paths: list[str] = []
        self._batch_folder: str | None = None
        layout.addWidget(self._batch_bar)

        layout.addSpacing(6)

        transcript_header = QHBoxLayout()
        transcript_header.setSpacing(8)
        transcript_label = QLabel("TRANSCRIPT")
        transcript_label.setObjectName("transcriptCaption")
        transcript_header.addWidget(transcript_label)
        transcript_header.addStretch(1)
        button_row = transcript_header
        self.save_button = QPushButton("Save Transcript")
        self.save_button.setObjectName("primaryOutlineButton")
        self.save_button.setEnabled(False)
        self.save_button.setFixedHeight(32)
        self.save_button.setCursor(Qt.PointingHandCursor)
        self.save_button.setIcon(_icon_save(16, ACCENT))
        self.save_button.setIconSize(QSize(15, 15))
        self.save_button.clicked.connect(self.save_transcript)
        button_row.addWidget(self.save_button)

        self.copy_button = QPushButton("Copy")
        self.copy_button.setObjectName("secondaryButton")
        self.copy_button.setEnabled(False)
        self.copy_button.setFixedHeight(32)
        self.copy_button.setCursor(Qt.PointingHandCursor)
        self.copy_button.setIcon(_icon_copy(16, TEXT_PRIMARY))
        self.copy_button.setIconSize(QSize(15, 15))
        self.copy_button.clicked.connect(self.copy_transcript)
        button_row.addWidget(self.copy_button)

        self.clear_button = QPushButton("Clear")
        self.clear_button.setObjectName("ghostButton")
        self.clear_button.setEnabled(False)
        self.clear_button.setFixedHeight(32)
        self.clear_button.setCursor(Qt.PointingHandCursor)
        self.clear_button.setIcon(_icon_clear(16, TEXT_MUTED))
        self.clear_button.setIconSize(QSize(15, 15))
        self.clear_button.clicked.connect(self.clear_transcript)
        button_row.addWidget(self.clear_button)

        layout.addLayout(transcript_header)
        layout.addSpacing(2)


        self.transcript_area = QTextEdit()
        self.transcript_area.setObjectName("transcriptArea")
        self.transcript_area.setProperty("hasContent", False)
        self.transcript_area.setReadOnly(True)
        self.transcript_area.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.transcript_area.customContextMenuRequested.connect(
            self._transcript_context_menu
        )
        self.transcript_area.setFrameShape(QTextEdit.NoFrame)
        self.transcript_area.setPlaceholderText(
            "Click Start Recording, speak, then click Stop Recording. "
            "Or import audio, or drop files or a folder on this window. "
            "Your transcribed text will appear here."
        )
        self.transcript_area.setAcceptDrops(False)
        self.transcript_area.setMinimumHeight(150)
        self.transcript_area.textChanged.connect(self._update_save_button)
        layout.addWidget(self.transcript_area, stretch=1)

        layout.addSpacing(6)


        self.setCentralWidget(central)

        self._model_failed = False
        self._typing_lock = threading.Lock()
        # Set for "how are you? send it": press Enter once that text is typed.
        self._send_after_typing = False
        self._start_model_load()

        # Global hold-to-talk hotkey: works even when this window isn't
        # focused (or is hidden to tray), so you can click into another
        # app's text field, hold the hotkey, talk, release it, and the
        # transcribed text gets typed directly into that field.
        self._hotkey_bridge = HotkeyBridge()
        self._hotkey_bridge.press_requested.connect(self._handle_primary_press)
        self._hotkey_bridge.release_requested.connect(self._handle_hotkey_release)
        self._hotkey_bridge.alt_press_requested.connect(self._handle_alt_press)
        self._hotkey_bridge.alt_release_requested.connect(self._handle_hotkey_release)
        self._hotkey_bridge.redo_requested.connect(self._try_harder)
        self._hotkey_bridge.redo_too_late.connect(self._redo_too_late)
        self._last_typed_at = 0.0
        self._redo_hook = None
        self._redo_key_down = False
        # Try harder state: the last recording (memory only, see core/redo.py),
        # what was typed from it, and a loaded bigger model kept for reuse.
        self._last_audio: np.ndarray | None = None
        self._last_audio_params: tuple | None = None
        self._redo: dict | None = None
        self._redo_armed = False
        self._redo_worker: TranscribeThread | None = None
        self._redo_model: tuple[str, Transcriber] | None = None
        self._redo_model_timer = QTimer(self)
        self._redo_model_timer.setSingleShot(True)
        # A bigger model holds 1-3 GB of memory; let it go after a quiet spell.
        self._redo_model_timer.timeout.connect(lambda: setattr(self, "_redo_model", None))
        self._redo_expiry_timer = QTimer(self)
        self._redo_expiry_timer.setSingleShot(True)
        self._redo_expiry_timer.timeout.connect(self._clear_redo)
        self._alt_press_hook = None
        self._alt_release_hook = None
        self._hotkey_press_hook = None
        self._hotkey_release_hook = None
        self._hotkey_registration_error: str | None = None

        history_label = QLabel("TODAY")
        history_label.setObjectName("transcriptCaption")
        layout.addWidget(history_label)

        history_scroll = QScrollArea()
        history_scroll.setObjectName("historyScroll")
        history_scroll.setWidgetResizable(True)
        history_scroll.setFrameShape(QScrollArea.NoFrame)
        history_scroll.setFixedHeight(96)
        history_content = QWidget()
        self._history_feed_layout = QVBoxLayout(history_content)
        self._history_feed_layout.setContentsMargins(0, 0, 0, 0)
        self._history_feed_layout.setSpacing(0)
        self._history_feed_layout.addStretch(1)
        history_scroll.setWidget(history_content)
        layout.addWidget(history_scroll)

        self._build_insights_page()
        self._switch_page(0)
        self._refresh_history_feed()

        self._register_global_hotkey()
        self._sync_ready_stream()

        self._setup_tray_icon()
        self._announce_whats_new()

        self._update_checker: UpdateCheckThread | None = None
        self._update_downloader: UpdateDownloadThread | None = None
        self._pending_update_info: UpdateInfo | None = None
        self._downloaded_installer_path: str | None = None
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
        # to discover it's running or why the hotkey doesn't work. Show the window
        # so the warning label above is actually seen.
        if self._hotkey_registration_error and self.tray_icon is None:
            self._show_and_raise()

    # -- hotkey registration ------------------------------------------------

    def _sync_ready_stream(self) -> None:
        """Opens or closes the always-on mic stream to match the "keep
        microphone ready" setting and the chosen device. Never touches a
        stream that is mid-recording."""
        want = hotkey_settings.get_keep_mic_ready_enabled()
        device = resolve_input_device(hotkey_settings.get_input_device())
        if self._ready_stream is not None and (not want or device != self._ready_device):
            if self.stream is self._ready_stream:
                return
            try:
                self._ready_stream.stop()
                self._ready_stream.close()
            except Exception:  # noqa: BLE001
                pass
            self._ready_stream = None
            self._ready_buffer = None
        if not want or self._ready_stream is not None:
            return

        rate = device_native_samplerate(device)
        buffer = RollingBuffer(int(rate * 0.5))

        def callback(indata, frames, time_info, status):  # noqa: ANN001
            chunk = indata[:, 0].copy()
            if self._capturing:
                self._chunks.append(chunk)
                self._indicator.feed_audio(chunk)
            else:
                buffer.push(chunk)

        try:
            stream = sd.InputStream(
                samplerate=rate, channels=1, dtype="float32", device=device, callback=callback
            )
            stream.start()
        except Exception:  # noqa: BLE001
            # No mic or device busy: fall back to opening it per recording.
            return
        self._ready_stream = stream
        self._ready_buffer = buffer
        self._ready_rate = rate
        self._ready_device = device

    def _register_global_hotkey(self) -> None:
        """(Re)registers the global hold-to-talk hotkey as self._hotkey.
        Safe to call again after changing the hotkey (see
        _open_settings_dialog) -- unhooks the previous registration first."""
        for hook in (
            self._hotkey_press_hook,
            self._hotkey_release_hook,
            self._hold_other_hook,
            self._alt_press_hook,
            self._alt_release_hook,
            self._redo_hook,
        ):
            if hook is not None:
                try:
                    keyboard.unhook(hook)
                except (KeyError, ValueError):
                    pass
        self._hotkey_press_hook = None
        self._hotkey_release_hook = None
        self._hold_other_hook = None
        self._alt_press_hook = None
        self._alt_release_hook = None
        self._redo_hook = None
        self._hold_gate = None
        self._hotkey_registration_error = None

        try:
            if self._hotkey in hotkey_settings.HOLD_DELAY_HOTKEYS:
                # A key you also type with (Shift): only counts as the
                # hotkey when held alone for a moment, see core/hold_gate.py.
                gate = HoldGate(
                    on_activate=self._hotkey_bridge.press_requested.emit,
                    on_deactivate=self._hotkey_bridge.release_requested.emit,
                )
                self._hold_gate = gate
                own_codes = {42, 54}  # left and right Shift scan codes

                def _other_modifier_held() -> bool:
                    return any(keyboard.is_pressed(m) for m in ("ctrl", "alt", "windows"))

                def _on_any_key(event) -> None:  # noqa: ANN001
                    if event.event_type == "down" and event.scan_code not in own_codes:
                        gate.other_key_down()

                self._hotkey_press_hook = keyboard.on_press_key(
                    self._hotkey, lambda e: gate.key_down(_other_modifier_held())
                )
                self._hotkey_release_hook = keyboard.on_release_key(
                    self._hotkey, lambda e: gate.key_up()
                )
                self._hold_other_hook = keyboard.hook(_on_any_key)
            else:
                self._hotkey_press_hook = keyboard.on_press_key(
                    self._hotkey, lambda e: self._hotkey_bridge.press_requested.emit()
                )
                self._hotkey_release_hook = keyboard.on_release_key(
                    self._hotkey, lambda e: self._hotkey_bridge.release_requested.emit()
                )
            second = hotkey_settings.get_second_hotkey()
            if second and second != self._hotkey and hotkey_license.is_pro():
                self._alt_press_hook = keyboard.on_press_key(
                    second, lambda e: self._hotkey_bridge.alt_press_requested.emit()
                )
                self._alt_release_hook = keyboard.on_release_key(
                    second, lambda e: self._hotkey_bridge.alt_release_requested.emit()
                )
            redo_key = hotkey_settings.get_redo_hotkey()
            if redo_key and redo_key not in (self._hotkey, second):
                self._redo_hook = keyboard.hook_key(redo_key, self._on_redo_key, suppress=True)
        except Exception as exc:  # noqa: BLE001
            # Global hooks can fail without admin rights on some systems;
            # the app still works fine via the on-screen button, but the
            # user needs to actually be told the hotkey won't work --
            # silently swallowing this left them with no clue why
            # dictating into other apps never did anything.
            self._hotkey_registration_error = str(exc)

        self._update_hotkey_hint()

    def _refresh_language_badge(self) -> None:
        """Keeps the dictation-language badge (top-right, next to the
        settings gear) in sync with the persisted setting -- so the current
        language is visible at a glance in the main window itself, not only
        inside the Settings dialog."""
        code = hotkey_settings.get_language()
        name = next(
            (n for c, n in hotkey_settings.AVAILABLE_LANGUAGES if c == code), "Auto-detect"
        )
        self.language_badge.setText(name)

    def _update_hotkey_hint(self) -> None:
        if self._hotkey_registration_error:
            # No room for the icon/badge layout here -- collapse to one
            # full-width error line instead.
            self._hotkey_hint_icon.hide()
            self._hotkey_hint_prefix.hide()
            self._hotkey_badge.hide()
            self._hotkey_hint_suffix.setObjectName("hotkeyHintError")
            self._hotkey_hint_suffix.setText(
                f"Global {self._hotkey.upper()} hotkey unavailable "
                f"({self._hotkey_registration_error}). Use the Start/Stop button above instead."
            )
        else:
            self._hotkey_hint_icon.show()
            self._hotkey_hint_prefix.show()
            self._hotkey_badge.show()
            self._hotkey_badge.setText(self._hotkey.upper())
            self._hotkey_hint_suffix.setObjectName("hotkeyHint")
            self._hotkey_hint_suffix.setText(
                "anywhere to talk, release to stop. Text is typed directly "
                "into whatever you're focused on."
            )
        self._hotkey_hint_suffix.style().unpolish(self._hotkey_hint_suffix)
        self._hotkey_hint_suffix.style().polish(self._hotkey_hint_suffix)

    @staticmethod
    def _new_settings_combo() -> QComboBox:
        """A QComboBox wouldn't otherwise shrink below its longest item's
        unwrapped text width (confirmed via measurement: one combo alone
        demanded 439px), which forced the whole Settings dialog wider than
        its fixed width and produced an unwanted horizontal scrollbar. The
        adjust policy below caps how much the closed box's *own* width
        counts toward its size hint -- the dropdown popup still shows full,
        untruncated item text regardless."""
        combo = _NoWheelComboBox()
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(20)
        combo.setMinimumHeight(36)
        return combo

    def _open_settings_dialog(self) -> None:
        """Opens Settings as a full page inside the main window: a category
        list on the left and the chosen category's controls on the right,
        grouped by what the settings do. Reachable from the sidebar's
        Settings button, the language badge and the tray menu. Nothing is
        saved until "Save changes"; "Cancel" (or leaving through the sidebar)
        discards."""
        self._show_and_raise()
        if getattr(self, "_settings_close", None) is not None:
            self._settings_close(False)

        dialog = QWidget()
        dialog.setObjectName("settingsPage")
        dialog.setStyleSheet(SETTINGS_DIALOG_STYLESHEET)

        outer_layout = QVBoxLayout(dialog)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        header = QWidget()
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(28, 18, 28, 14)
        header_row.setSpacing(10)
        header_title = QLabel("Settings")
        header_title.setObjectName("settingsPageTitle")
        header_row.addWidget(header_title)
        header_row.addStretch(1)
        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("ghostButton")
        cancel_button.setCursor(Qt.PointingHandCursor)
        save_button = QPushButton("Save changes")
        save_button.setObjectName("primaryOutlineButton")
        save_button.setCursor(Qt.PointingHandCursor)
        header_row.addWidget(cancel_button)
        header_row.addWidget(save_button)
        outer_layout.addWidget(header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        outer_layout.addLayout(body, stretch=1)

        nav = QWidget()
        nav.setObjectName("settingsNav")
        nav.setFixedWidth(168)
        nav_layout = QVBoxLayout(nav)
        nav_layout.setContentsMargins(12, 4, 12, 12)
        nav_layout.setSpacing(4)
        body.addWidget(nav)

        section_stack = QStackedWidget()
        body.addWidget(section_stack, stretch=1)

        section_buttons: list[QPushButton] = []

        def _show_section(index: int) -> None:
            section_stack.setCurrentIndex(index)
            for i, btn in enumerate(section_buttons):
                btn.setChecked(i == index)

        def _new_section(title: str, subtitle: str) -> QVBoxLayout:
            index = len(section_buttons)
            btn = QPushButton(title)
            btn.setObjectName("sidebarNavButton")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setCheckable(True)
            btn.setMinimumHeight(36)
            btn.clicked.connect(lambda: _show_section(index))
            nav_layout.addWidget(btn)
            section_buttons.append(btn)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            page_content = QWidget()
            page_content.setMaximumWidth(620)
            page_layout = QVBoxLayout(page_content)
            page_layout.setContentsMargins(28, 4, 28, 24)
            page_layout.setSpacing(14)
            title_label = QLabel(title)
            title_label.setObjectName("settingsPageTitle")
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("settingsPageSubtitle")
            subtitle_label.setWordWrap(True)
            page_layout.addWidget(title_label)
            page_layout.addWidget(subtitle_label)
            page_layout.addSpacing(6)
            page_layout.addStretch(1)
            holder = QWidget()
            holder_row = QHBoxLayout(holder)
            holder_row.setContentsMargins(0, 0, 0, 0)
            holder_row.addWidget(page_content, stretch=1)
            holder_row.addStretch(0)
            scroll.setWidget(holder)
            section_stack.addWidget(scroll)
            return page_layout

        def _add(page_layout: QVBoxLayout, item) -> None:  # noqa: ANN001
            if isinstance(item, QWidget):
                page_layout.insertWidget(page_layout.count() - 1, item)
            else:
                page_layout.insertLayout(page_layout.count() - 1, item)

        general_layout = _new_section("General", "Hotkey, language, model and startup.")
        audio_layout = _new_section("Audio", "Microphone and how text is typed.")
        text_layout = _new_section("Text", "How the transcript is cleaned and corrected.")
        pro_layout = _new_section("Pro", "License and the Pro dictation tools.")
        files_layout = _new_section("Files", "Importing audio and video files.")
        privacy_layout = _new_section("Privacy", "Network use and where VoxScribe stays quiet.")
        about_layout = _new_section("About", "Version, updates and usage.")
        nav_layout.addStretch(1)
        _show_section(0)

        class _SectionProxy:
            """Lets the long builder below keep calling layout.addWidget /
            addLayout while the target section is switched with ``layout =``."""

            def __init__(self, target: QVBoxLayout) -> None:
                self._target = target

            def addWidget(self, widget) -> None:  # noqa: ANN001, N802
                _add(self._target, widget)

            def addLayout(self, other) -> None:  # noqa: ANN001, N802
                _add(self._target, other)

        general = _SectionProxy(general_layout)
        audio = _SectionProxy(audio_layout)
        text = _SectionProxy(text_layout)
        pro = _SectionProxy(pro_layout)
        files = _SectionProxy(files_layout)
        privacy = _SectionProxy(privacy_layout)
        about = _SectionProxy(about_layout)
        layout = pro

        license_section_label = QLabel("VOXSCRIBE PRO")
        license_section_label.setObjectName("settingsSectionLabel")
        layout.addWidget(license_section_label)

        license_status_label = QLabel()
        license_status_label.setWordWrap(True)
        license_status_label.setObjectName("settingsHint")
        layout.addWidget(license_status_label)

        license_benefits_label = QLabel(
            "What Pro adds:\n"
            "- Snippets: say a short trigger phrase and VoxScribe types a full block of "
            "text, with live {date}, {time} and {clipboard} variables.\n"
            "- Medium and Large Whisper models for higher accuracy (they need a faster PC).\n"
            "Everything else stays free, with no account."
        )
        license_benefits_label.setWordWrap(True)
        license_benefits_label.setObjectName("settingsHint")
        layout.addWidget(license_benefits_label)

        license_compare_label = QLabel(
            "Other dictation tools charge a yearly or monthly subscription, "
            "often well into the hundreds per year. VoxScribe Pro is $14 once."
        )
        license_compare_label.setWordWrap(True)
        license_compare_label.setObjectName("settingsHint")
        layout.addWidget(license_compare_label)

        license_buy_button = QPushButton("Get Pro ($14 once)")
        license_buy_button.setObjectName("primaryOutlineButton")
        license_buy_button.setCursor(Qt.PointingHandCursor)
        license_buy_button.clicked.connect(
            lambda: webbrowser.open("https://hmamster3.gumroad.com/l/tbsfom")
        )
        layout.addWidget(license_buy_button)

        license_key_edit = QLineEdit()
        license_key_edit.setPlaceholderText("Paste your license key")
        license_key_edit.setMinimumHeight(36)
        layout.addWidget(license_key_edit)

        license_button_row = QHBoxLayout()
        license_button_row.setSpacing(10)
        license_unlock_button = QPushButton("Unlock")
        license_unlock_button.setObjectName("secondaryButton")
        license_unlock_button.setCursor(Qt.PointingHandCursor)
        license_button_row.addWidget(license_unlock_button)
        license_remove_button = QPushButton("Remove license")
        license_remove_button.setObjectName("ghostButton")
        license_remove_button.setCursor(Qt.PointingHandCursor)
        license_button_row.addWidget(license_remove_button)
        layout.addLayout(license_button_row)

        def _refresh_license_ui() -> None:
            if hotkey_license.is_pro():
                license_status_label.setText(
                    "✓ Pro unlocked -- thank you for supporting VoxScribe."
                )
                license_benefits_label.hide()
                license_compare_label.hide()
                license_buy_button.hide()
                license_key_edit.hide()
                license_unlock_button.hide()
                license_remove_button.show()
            else:
                license_status_label.setText(
                    "Free tier. Paste a Pro license key below to unlock Snippets. "
                    "Needs internet once, to activate."
                )
                license_benefits_label.show()
                license_compare_label.show()
                license_buy_button.show()
                license_key_edit.show()
                license_unlock_button.show()
                license_remove_button.hide()

        def _try_unlock_license() -> None:
            key = license_key_edit.text()
            license_status_label.setText("Activating...")
            license_unlock_button.setEnabled(False)
            # Let the "Activating..." label actually paint before the
            # blocking network call below -- there's no QThread here (this
            # is a one-off, user-initiated click, not a recurring
            # background task), so without this the dialog would otherwise
            # look frozen for the duration of the request.
            QApplication.processEvents()

            ok, message = hotkey_license.activate_online(key)
            license_unlock_button.setEnabled(True)
            if not ok:
                license_status_label.setText(message or "Activation failed -- try again.")
                return

            if hotkey_license.set_license_key(key):
                license_key_edit.clear()
                _refresh_license_ui()
            else:
                # Passed online activation but failed local verification --
                # shouldn't happen (activate_online already checks this
                # first), but don't silently claim success if it somehow did.
                license_status_label.setText(
                    "That key isn't valid -- check for typos and try again."
                )

        def _remove_license() -> None:
            # Frees this PC's slot on the server first, so the key can move to
            # a new PC without writing to support. Removed here either way.
            key = hotkey_license.get_license_key() or ""
            license_status_label.setText("Removing...")
            license_remove_button.setEnabled(False)
            QApplication.processEvents()
            ok, message = hotkey_license.deactivate_online(key)
            license_remove_button.setEnabled(True)
            hotkey_license.clear_license_key()
            _refresh_license_ui()
            if ok:
                license_status_label.setText(
                    "License removed from this PC. The key is free to use on another PC."
                )
            else:
                license_status_label.setText(
                    "License removed from this PC, but the server could not be reached, "
                    f"so this PC may still count as one of the key's two. ({message}) "
                    "Unlock and remove again when online to free it."
                )

        license_unlock_button.clicked.connect(_try_unlock_license)
        license_remove_button.clicked.connect(_remove_license)
        _refresh_license_ui()

        layout = general
        hotkey_label = QLabel("HOLD-TO-TALK HOTKEY")
        hotkey_label.setObjectName("settingsSectionLabel")
        layout.addWidget(hotkey_label)

        combo = self._new_settings_combo()
        for key in hotkey_settings.AVAILABLE_HOTKEYS:
            combo.addItem(key.upper(), key)
        combo.setCurrentIndex(hotkey_settings.AVAILABLE_HOTKEYS.index(self._hotkey))
        layout.addWidget(combo)

        hotkey_hint = QLabel(
            "LEFT SHIFT works by holding it alone for about a third of a second. "
            "Typing capitals, or Shift with another key, never triggers it. "
            "Shift+click selection isn't detected, so a long Shift+click can start a recording."
        )
        hotkey_hint.setObjectName("settingsHint")
        hotkey_hint.setWordWrap(True)
        layout.addWidget(hotkey_hint)

        talk_mode_combo = self._new_settings_combo()
        for mode, label in hotkey_settings.AVAILABLE_TALK_MODES:
            talk_mode_combo.addItem(label, mode)
        current_talk_mode = hotkey_settings.get_talk_mode()
        for i in range(talk_mode_combo.count()):
            if talk_mode_combo.itemData(i) == current_talk_mode:
                talk_mode_combo.setCurrentIndex(i)
                break
        layout.addWidget(talk_mode_combo)

        layout = audio
        mic_label = QLabel("MICROPHONE")
        mic_label.setObjectName("settingsSectionLabel")
        layout.addWidget(mic_label)

        mic_combo = self._new_settings_combo()
        mic_combo.addItem("Auto-detect (recommended)", None)
        for idx, name in list_input_devices():
            mic_combo.addItem(name, idx)
        current_device = hotkey_settings.get_input_device()
        for i in range(mic_combo.count()):
            if mic_combo.itemData(i) == current_device:
                mic_combo.setCurrentIndex(i)
                break
        layout.addWidget(mic_combo)

        mic_test_button = QPushButton("Test microphone")
        mic_test_button.setObjectName("secondaryButton")
        mic_test_button.setCursor(Qt.PointingHandCursor)
        layout.addWidget(mic_test_button)

        mic_level_bar = QProgressBar()
        mic_level_bar.setObjectName("micLevelMeter")
        mic_level_bar.setRange(0, 100)
        mic_level_bar.setTextVisible(False)
        mic_level_bar.hide()
        layout.addWidget(mic_level_bar)

        mic_test_status = QLabel("")
        mic_test_status.setObjectName("settingsHint")
        mic_test_status.setWordWrap(True)
        mic_test_status.hide()
        layout.addWidget(mic_test_status)

        keep_ready_checkbox = QCheckBox("Keep microphone ready (never clip the first word)")
        keep_ready_checkbox.setChecked(hotkey_settings.get_keep_mic_ready_enabled())
        layout.addWidget(keep_ready_checkbox)

        keep_ready_hint = QLabel(
            "Keeps the mic open and remembers the last half second in memory only, "
            "so your first word isn't cut off by the mic starting up. Nothing is "
            "saved or transcribed until you hold the hotkey. Windows will show the "
            "mic as in use, and a Bluetooth headset may stay in its lower quality "
            "call mode. Off by default."
        )
        keep_ready_hint.setObjectName("settingsHint")
        keep_ready_hint.setWordWrap(True)
        layout.addWidget(keep_ready_hint)

        mic_test_state: dict = {"thread": None, "timer": None, "peak_seen": 0.0}

        def _stop_mic_test(final_message: str | None = None) -> None:
            timer = mic_test_state["timer"]
            if timer is not None:
                timer.stop()
                mic_test_state["timer"] = None
            thread = mic_test_state["thread"]
            if thread is not None:
                thread.stop()
                thread.wait(1000)
                mic_test_state["thread"] = None
            mic_test_button.setText("Test microphone")
            mic_level_bar.hide()
            if final_message is not None:
                mic_test_status.setText(final_message)
                mic_test_status.show()
            else:
                mic_test_status.hide()

        def _on_mic_level(peak: float) -> None:
            mic_test_state["peak_seen"] = max(mic_test_state["peak_seen"], peak)
            mic_level_bar.setValue(min(100, int(peak * 100)))
            clipping = peak >= 0.98
            mic_level_bar.setProperty("clipping", clipping)
            mic_level_bar.style().unpolish(mic_level_bar)
            mic_level_bar.style().polish(mic_level_bar)
            mic_test_status.setText(
                "Clipping -- move back from the mic or lower input volume."
                if clipping
                else "Listening... talk normally."
            )

        def _on_mic_test_failed(message: str) -> None:
            _stop_mic_test(f"Couldn't test this microphone: {message}")

        def _on_mic_test_timeout() -> None:
            if mic_test_state["peak_seen"] < 0.03:
                _stop_mic_test(
                    "No signal detected -- check the selected device and that it isn't muted."
                )
            else:
                _stop_mic_test("Test complete -- levels looked good.")

        def _start_mic_test() -> None:
            device = resolve_input_device(mic_combo.currentData())
            mic_test_state["peak_seen"] = 0.0
            mic_level_bar.setValue(0)
            mic_level_bar.setProperty("clipping", False)
            mic_level_bar.show()
            mic_test_status.setText("Listening... talk normally.")
            mic_test_status.show()
            mic_test_button.setText("Stop test")

            thread = MicTestThread(device)
            thread.level.connect(_on_mic_level)
            thread.failed.connect(_on_mic_test_failed)
            thread.start()
            mic_test_state["thread"] = thread

            timer = QTimer(dialog)
            timer.setSingleShot(True)
            timer.timeout.connect(_on_mic_test_timeout)
            timer.start(5000)
            mic_test_state["timer"] = timer

        def _toggle_mic_test() -> None:
            if mic_test_state["thread"] is not None:
                _stop_mic_test()
            else:
                _start_mic_test()

        mic_test_button.clicked.connect(_toggle_mic_test)

        layout = general
        language_label = QLabel("DICTATION LANGUAGE")
        language_label.setObjectName("settingsSectionLabel")
        layout.addWidget(language_label)

        language_combo = self._new_settings_combo()
        for code, name in hotkey_settings.AVAILABLE_LANGUAGES:
            language_combo.addItem(name, code)
        current_language = hotkey_settings.get_language()
        for i in range(language_combo.count()):
            if language_combo.itemData(i) == current_language:
                language_combo.setCurrentIndex(i)
                break
        layout.addWidget(language_combo)

        layout = text
        translate_checkbox = QCheckBox("Translate to English")
        translate_checkbox.setChecked(hotkey_settings.get_translate_to_english_enabled())
        layout.addWidget(translate_checkbox)

        translate_hint = QLabel(
            "Speak in the language above, get English text out instead of a "
            "transcript in that language. Built into the Whisper model "
            "already running, no extra download."
        )
        translate_hint.setObjectName("settingsHint")
        translate_hint.setWordWrap(True)
        layout.addWidget(translate_hint)

        layout = general
        model_label = QLabel("SPEECH MODEL")
        model_label.setObjectName("settingsSectionLabel")
        layout.addWidget(model_label)

        model_combo = self._new_settings_combo()
        for size, label in hotkey_settings.AVAILABLE_MODEL_SIZES:
            model_combo.addItem(label, size)
        current_model_size = hotkey_settings.get_model_size()
        for i in range(model_combo.count()):
            if model_combo.itemData(i) == current_model_size:
                model_combo.setCurrentIndex(i)
                break
        layout.addWidget(model_combo)

        model_hint = QLabel(
            "Takes effect after restarting VoxScribe. Switching to a size not "
            "already downloaded needs internet on next launch."
        )
        model_hint.setObjectName("settingsHint")
        model_hint.setWordWrap(True)
        layout.addWidget(model_hint)

        # Speed depends on the PC far more than a label can say, so let people
        # measure it with their own voice before picking (app/speed_test.py).
        speed_row = QHBoxLayout()
        speed_test_button = QPushButton("Test speed on this PC...")
        speed_test_button.setObjectName("secondaryButton")
        speed_test_button.setCursor(Qt.PointingHandCursor)
        speed_test_button.setMinimumHeight(32)
        speed_test_button.clicked.connect(
            lambda: SpeedTestDialog(SETTINGS_DIALOG_STYLESHEET, self.transcriber, self).exec()
        )
        speed_row.addWidget(speed_test_button)
        speed_row.addStretch(1)
        layout.addLayout(speed_row)

        def _update_model_lock_state() -> None:
            unlocked = hotkey_license.is_pro()
            item_model = model_combo.model()
            for i in range(model_combo.count()):
                if model_combo.itemData(i) in hotkey_settings.PRO_MODEL_SIZES:
                    item_model.item(i).setEnabled(unlocked)
            hint = (
                "Faster models type sooner; more accurate ones get names and quiet "
                "speech right more often. Takes effect after restarting VoxScribe. "
                "A model not already downloaded needs internet on next launch."
            )
            if not unlocked:
                hint += " The three most accurate models need Pro."
            if model_combo.currentData() in hotkey_settings.NO_TRANSLATE_MODEL_SIZES:
                hint += (
                    " Large turbo cannot translate: Translate to English needs "
                    "another model."
                )
            model_hint.setText(hint)

        _update_model_lock_state()
        model_combo.currentIndexChanged.connect(_update_model_lock_state)
        license_unlock_button.clicked.connect(_update_model_lock_state)
        license_remove_button.clicked.connect(_update_model_lock_state)

        layout = text
        vocab_label = QLabel("CUSTOM VOCABULARY")
        vocab_label.setObjectName("settingsSectionLabel")
        layout.addWidget(vocab_label)

        vocab_edit = QLineEdit()
        vocab_edit.setPlaceholderText("e.g. VoxScribe, Ahmed, faster-whisper")
        vocab_edit.setText(", ".join(hotkey_settings.get_custom_vocabulary()))
        vocab_edit.setMinimumHeight(36)
        layout.addWidget(vocab_edit)

        vocab_hint = QLabel(
            "Names, acronyms, or terms Whisper tends to mishear, comma-separated. "
            "Nudges recognition toward them; doesn't guarantee a match."
        )
        vocab_hint.setObjectName("settingsHint")
        vocab_hint.setWordWrap(True)
        layout.addWidget(vocab_hint)

        replacements_label = QLabel("WORD REPLACEMENTS")
        replacements_label.setObjectName("settingsSectionLabel")
        layout.addWidget(replacements_label)

        replacements_edit = QTextEdit()
        replacements_edit.setPlainText(
            "\n".join(f"{a} => {b}" for a, b in replacements.get_replacements())
        )
        replacements_edit.setPlaceholderText("vox scribe => VoxScribe")
        replacements_edit.setFixedHeight(80)
        layout.addWidget(replacements_edit)

        replacements_hint = QLabel(
            "One per line: heard => replacement. Fixes words Whisper keeps getting "
            "wrong the same way. Whole words only, not case sensitive. Leave the "
            "right side empty to delete a word."
        )
        replacements_hint.setObjectName("settingsHint")
        replacements_hint.setWordWrap(True)
        layout.addWidget(replacements_hint)

        word_lists_row = QHBoxLayout()
        export_lists_button = QPushButton("Export word lists...")
        import_lists_button = QPushButton("Import word lists...")
        for button in (export_lists_button, import_lists_button):
            button.setObjectName("secondaryButton")
            button.setCursor(Qt.PointingHandCursor)
            word_lists_row.addWidget(button)
        word_lists_row.addStretch(1)
        layout.addLayout(word_lists_row)

        word_lists_result = QLabel(
            "One file with your vocabulary and replacements, for a backup, another "
            "PC or the Android app."
        )
        word_lists_result.setObjectName("settingsHint")
        word_lists_result.setWordWrap(True)
        layout.addWidget(word_lists_result)

        def _vocabulary_in_box() -> list[str]:
            return [t.strip() for t in vocab_edit.text().split(",") if t.strip()]

        def _export_word_lists() -> None:
            start = str(Path.home() / "Documents" / word_lists.DEFAULT_FILE_NAME)
            path, _ = QFileDialog.getSaveFileName(
                dialog, "Export word lists", start, "VoxScribe word lists (*.json)"
            )
            if not path:
                return
            vocabulary = _vocabulary_in_box()
            pairs = replacements.parse_replacements_text(replacements_edit.toPlainText())
            try:
                Path(path).write_text(word_lists.export_text(vocabulary, pairs), encoding="utf-8")
            except OSError as exc:
                word_lists_result.setText(f"Could not save the file: {exc}")
                return
            word_lists_result.setText(
                f"Saved {len(vocabulary)} vocabulary term{'s' if len(vocabulary) != 1 else ''} "
                f"and {len(pairs)} replacement{'s' if len(pairs) != 1 else ''} "
                f"to {Path(path).name}."
            )

        def _import_word_lists() -> None:
            path, _ = QFileDialog.getOpenFileName(
                dialog,
                "Import word lists",
                str(Path.home() / "Documents"),
                "Word lists (*.json *.txt);;All files (*)",
            )
            if not path:
                return
            try:
                vocabulary, pairs = word_lists.parse_import(
                    Path(path).read_text(encoding="utf-8", errors="replace")
                )
            except (OSError, ValueError) as exc:
                word_lists_result.setText(str(exc))
                return
            current_vocabulary = _vocabulary_in_box()
            merged_vocabulary = vocab_learner.merge_vocabulary(current_vocabulary, vocabulary)
            new_terms = len(merged_vocabulary) - len(current_vocabulary)
            current_pairs = replacements.parse_replacements_text(replacements_edit.toPlainText())
            merged_pairs, added, changed = word_lists.merge_replacements(current_pairs, pairs)
            vocab_edit.setText(", ".join(merged_vocabulary))
            replacements_edit.setPlainText("\n".join(f"{a} => {b}" for a, b in merged_pairs))
            if not (new_terms or added or changed):
                word_lists_result.setText(
                    "Nothing new in that file. Your lists already have it all."
                )
                return
            parts = [
                f"{new_terms} vocabulary term{'s' if new_terms != 1 else ''}",
                f"{added} replacement{'s' if added != 1 else ''}",
            ]
            changed_note = f", and changed {changed}" if changed else ""
            word_lists_result.setText(
                f"Added {parts[0]} and {parts[1]}{changed_note}. "
                "Review them above, then press Save."
            )

        export_lists_button.clicked.connect(_export_word_lists)
        import_lists_button.clicked.connect(_import_word_lists)

        layout = pro
        snippets_label = QLabel("SNIPPETS (PRO)")
        snippets_label.setObjectName("settingsSectionLabel")
        layout.addWidget(snippets_label)

        snippets_edit = QTextEdit()
        snippets_edit.setPlainText(
            "\n".join(f"{trigger} => {expansion}" for trigger, expansion in snippets.get_snippets())
        )
        snippets_edit.setFixedHeight(90)
        layout.addWidget(snippets_edit)

        snippets_hint = QLabel(
            "One per line: trigger phrase => text to type instead. Say the "
            "trigger alone to expand it. Expansions can include {date}, "
            "{time}, or {clipboard} -- filled in live each time."
        )
        snippets_hint.setObjectName("settingsHint")
        snippets_hint.setWordWrap(True)
        layout.addWidget(snippets_hint)

        def _update_snippets_lock_state() -> None:
            unlocked = hotkey_license.is_pro()
            snippets_edit.setEnabled(unlocked)
            snippets_hint.setText(
                (
                    "One per line: trigger phrase => text to type instead. Say the "
                    "trigger alone to expand it. Expansions can include {date}, "
                    "{time}, or {clipboard} -- filled in live each time."
                )
                if unlocked
                else "Unlock Pro above to set up snippets."
            )

        _update_snippets_lock_state()
        license_unlock_button.clicked.connect(_update_snippets_lock_state)
        license_remove_button.clicked.connect(_update_snippets_lock_state)

        templates_label = QLabel("FILL-IN TEMPLATES (PRO)")
        templates_label.setObjectName("settingsSectionLabel")
        layout.addWidget(templates_label)

        templates_edit = QTextEdit()
        templates_edit.setPlainText(templates.format_lines(templates.get_templates()))
        templates_edit.setPlaceholderText("bug report => Title: {title}\\nSteps: {steps}")
        templates_edit.setFixedHeight(90)
        layout.addWidget(templates_edit)

        templates_hint = QLabel(
            "One per line: name => text with {slots}. Use \\n for a line break. "
            'Say "template <name>" and VoxScribe asks for each slot in turn; say '
            '"skip" to leave one empty or "cancel" to stop. {date} and {time} '
            "fill themselves in."
        )
        templates_hint.setObjectName("settingsHint")
        templates_hint.setWordWrap(True)
        layout.addWidget(templates_hint)

        layout = text
        mode_label = QLabel("DICTATION MODE")
        mode_label.setObjectName("settingsSectionLabel")
        layout.addWidget(mode_label)
        mode_combo = self._new_settings_combo()
        for mode_name, mode_text in modes.MODE_LABELS.items():
            mode_combo.addItem(mode_text, mode_name)
        mode_combo.setCurrentIndex(max(0, mode_combo.findData(hotkey_settings.get_mode())))
        layout.addWidget(mode_combo)
        auto_modes_checkbox = QCheckBox("Switch modes by app automatically (Pro)")
        auto_modes_checkbox.setChecked(hotkey_settings.get_auto_modes_enabled())
        layout.addWidget(auto_modes_checkbox)
        mode_hint = QLabel(
            "Chat: tidy text and no full stop at the end of a one-line message. "
            "Email: full sentences with punctuation. Code: code dictation. Notes: "
            "tidy text, nothing rewritten. With Pro and automatic switching, chat "
            "apps (Slack, Discord, WhatsApp, Teams) use Chat, Outlook and Thunderbird "
            "use Email, code editors and terminals use Code, and Word, Notion, Obsidian "
            "and Notepad use Notes; every other app uses the mode above. Decided from "
            "the program's name only, never from the screen."
        )
        mode_hint.setObjectName("settingsHint")
        mode_hint.setWordWrap(True)
        layout.addWidget(mode_hint)

        def _update_mode_lock_state() -> None:
            unlocked = hotkey_license.is_pro()
            item_model = mode_combo.model()
            for i in range(mode_combo.count()):
                if mode_combo.itemData(i) in modes.PRO_MODES:
                    item_model.item(i).setEnabled(unlocked)
            auto_modes_checkbox.setEnabled(unlocked)

        _update_mode_lock_state()
        license_unlock_button.clicked.connect(_update_mode_lock_state)
        license_remove_button.clicked.connect(_update_mode_lock_state)

        layout = general
        second_label = QLabel("SECOND LANGUAGE KEY (PRO)")
        second_label.setObjectName("settingsSectionLabel")
        layout.addWidget(second_label)

        second_row = QHBoxLayout()
        second_key_combo = QComboBox()
        second_key_combo.addItem("Off", "")
        for key in hotkey_settings.AVAILABLE_HOTKEYS:
            if key not in hotkey_settings.HOLD_DELAY_HOTKEYS:
                second_key_combo.addItem(key.upper(), key)
        second_key_combo.setCurrentIndex(
            max(0, second_key_combo.findData(hotkey_settings.get_second_hotkey()))
        )
        second_language_combo = QComboBox()
        for code, name in hotkey_settings.AVAILABLE_LANGUAGES:
            second_language_combo.addItem(name, code)
        second_language_combo.setCurrentIndex(
            max(0, second_language_combo.findData(hotkey_settings.get_second_language()))
        )
        second_row.addWidget(second_key_combo)
        second_row.addWidget(second_language_combo, stretch=1)
        layout.addLayout(second_row)

        second_hint = QLabel(
            "Hold this key instead of the main one to dictate in the second language, "
            "with no trip to Settings. Useful if you switch between two languages."
        )
        second_hint.setObjectName("settingsHint")
        second_hint.setWordWrap(True)
        layout.addWidget(second_hint)

        redo_label = QLabel("TRY HARDER KEY")
        redo_label.setObjectName("settingsSectionLabel")
        layout.addWidget(redo_label)
        redo_key_combo = QComboBox()
        redo_key_combo.addItem("Off", "")
        for key in hotkey_settings.AVAILABLE_HOTKEYS:
            if key not in hotkey_settings.HOLD_DELAY_HOTKEYS:
                redo_key_combo.addItem(key.upper(), key)
        redo_key_combo.setCurrentIndex(
            max(0, redo_key_combo.findData(hotkey_settings.get_redo_hotkey()))
        )
        layout.addWidget(redo_key_combo)
        redo_hint = QLabel(
            "A word came out wrong? Press this key within 2 minutes and VoxScribe "
            "runs the same recording again through a bigger model and retypes only "
            "what changed. Free uses Small; Pro uses Large turbo, Large or Medium, "
            "whichever is downloaded. With no bigger model, the model in use runs again "
            "in careful mode. The key works normally in other apps the rest of the "
            "time, and the recording is kept in memory only."
        )
        redo_hint.setObjectName("settingsHint")
        redo_hint.setWordWrap(True)
        layout.addWidget(redo_hint)

        layout = pro
        profiles_label = QLabel("PER-APP PROFILES (PRO)")
        profiles_label.setObjectName("settingsSectionLabel")
        layout.addWidget(profiles_label)

        profiles_edit = QTextEdit()
        profiles_edit.setPlainText(app_profiles.format_lines(app_profiles.get_profiles()))
        profiles_edit.setPlaceholderText("code.exe => code=on, cleanup=off, language=en")
        profiles_edit.setFixedHeight(80)
        layout.addWidget(profiles_edit)

        profiles_hint = QLabel(
            "One per line: program.exe => option=value, ... Options: mode (chat, "
            "email, code, notes or default), language (a code like en or ar, or auto), "
            "cleanup, voice_commands, code, smart, period (on or off). Applies while "
            "that program has focus; anything not set uses the mode, then your normal "
            "settings."
        )
        profiles_hint.setObjectName("settingsHint")
        profiles_hint.setWordWrap(True)
        layout.addWidget(profiles_hint)

        layout = pro
        pro_tools_label = QLabel("PRO TOOLS")
        pro_tools_label.setObjectName("settingsSectionLabel")
        layout.addWidget(pro_tools_label)

        code_checkbox = QCheckBox("Code dictation")
        code_checkbox.setChecked(hotkey_settings.get_code_dictation_enabled())
        layout.addWidget(code_checkbox)

        code_hint = QLabel(
            'Say "camel case user name" to type userName, or "snake case", "pascal '
            'case", "kebab case", "constant case". Symbols by voice: "open paren", '
            '"equals", "dot", "new line". Turns off filler cleanup and capital '
            "letters while it is on."
        )
        code_hint.setObjectName("settingsHint")
        code_hint.setWordWrap(True)
        layout.addWidget(code_hint)

        smart_checkbox = QCheckBox("Smart formatting")
        smart_checkbox.setChecked(hotkey_settings.get_smart_formatting_enabled())
        layout.addWidget(smart_checkbox)

        smart_hint = QLabel(
            'Spoken emails, web addresses and numbers typed as written: "john at '
            'gmail dot com" becomes john@gmail.com, "twenty five percent" becomes 25%.'
        )
        smart_hint.setObjectName("settingsHint")
        smart_hint.setWordWrap(True)
        layout.addWidget(smart_hint)

        layout = files
        caption_label = QLabel("CAPTION LINE LENGTH")
        caption_label.setObjectName("settingsSectionLabel")
        layout.addWidget(caption_label)

        caption_spin = _NoWheelSpinBox()
        caption_spin.setRange(0, hotkey_settings.MAX_CAPTION_LINE_CHARS)
        caption_spin.setSpecialValueText("Off (keep Whisper's segments)")
        caption_spin.setValue(hotkey_settings.get_caption_line_chars())
        caption_spin.setSuffix(" characters")
        caption_spin.setMinimumHeight(36)
        layout.addWidget(caption_spin)

        caption_hint = QLabel(
            "Long captions in an imported .srt or .vtt are split into cards of at most "
            "two lines this long, with the timing shared out by text length. 42 is the "
            "usual guideline for YouTube and broadcast. Free, no Pro needed."
        )
        caption_hint.setObjectName("settingsHint")
        caption_hint.setWordWrap(True)
        layout.addWidget(caption_hint)

        speakers_label = QLabel("SPEAKER LABELS (PRO)")
        speakers_label.setObjectName("settingsSectionLabel")
        layout.addWidget(speakers_label)

        speakers_row = QHBoxLayout()
        speaker_count_combo = _NoWheelComboBox()
        speaker_count_combo.addItem("Detect", 0)
        for count in range(2, 9):
            speaker_count_combo.addItem(f"{count} speakers", count)
        speaker_count_combo.setCurrentIndex(
            max(0, speaker_count_combo.findData(hotkey_settings.get_speaker_count()))
        )
        speaker_names_edit = QLineEdit()
        speaker_names_edit.setPlaceholderText("Names in order of first speaking, e.g. Sam, Alex")
        speaker_names_edit.setText(", ".join(hotkey_settings.get_speaker_names()))
        speakers_row.addWidget(speaker_count_combo)
        speakers_row.addWidget(speaker_names_edit, stretch=1)
        layout.addLayout(speakers_row)

        speakers_hint = QLabel(
            "Used when you tick \"Label who is speaking\" while importing a file. "
            "Set the number of speakers if the automatic count is wrong. Names "
            "replace Speaker 1, Speaker 2 in the order each person first speaks."
        )
        speakers_hint.setObjectName("settingsHint")
        speakers_hint.setWordWrap(True)
        layout.addWidget(speakers_hint)

        layout = privacy
        offline_checkbox = QCheckBox("Offline mode: block all network use")
        offline_checkbox.setChecked(hotkey_settings.get_offline_mode_enabled())
        layout.addWidget(offline_checkbox)

        offline_hint = QLabel(
            "While on, VoxScribe cannot reach the internet at all: no launch ping, "
            "no update check, no model download. The connection log shows every "
            "outside connection VoxScribe has tried."
        )
        offline_hint.setObjectName("settingsHint")
        offline_hint.setWordWrap(True)
        layout.addWidget(offline_hint)

        log_button = QPushButton("View connection log")
        learn_button = QPushButton("Learn vocabulary from a folder")
        for button in (log_button, learn_button):
            button.setObjectName("secondaryButton")
            button.setCursor(Qt.PointingHandCursor)
        layout.addWidget(log_button)

        learn_result = QLabel("")
        learn_result.setObjectName("settingsHint")
        learn_result.setWordWrap(True)
        text.addWidget(learn_button)
        text.addWidget(learn_result)

        def _show_connection_log() -> None:
            self._open_connection_log(dialog)

        def _learn_vocabulary() -> None:
            folder = QFileDialog.getExistingDirectory(dialog, "Choose a folder of your files")
            if not folder:
                return
            learned = vocab_learner.learn_from_folder(folder)
            current = [t.strip() for t in vocab_edit.text().split(",") if t.strip()]
            merged = vocab_learner.merge_vocabulary(current, learned)
            added = len(merged) - len(current)
            vocab_edit.setText(", ".join(merged))
            learn_result.setText(
                f"Added {added} term{'s' if added != 1 else ''} to your custom "
                "vocabulary above. Review them, then press Save."
                if added
                else "No new terms found. Files are read on this PC only."
            )

        log_button.clicked.connect(_show_connection_log)
        learn_button.clicked.connect(_learn_vocabulary)

        def _update_pro_tools_lock_state() -> None:
            unlocked = hotkey_license.is_pro()
            for widget in (
                templates_edit,
                code_checkbox,
                smart_checkbox,
                speaker_count_combo,
                speaker_names_edit,
                second_key_combo,
                second_language_combo,
                profiles_edit,
                offline_checkbox,
                log_button,
                learn_button,
            ):
                widget.setEnabled(unlocked)
            if not unlocked:
                templates_hint.setText("Unlock Pro above to use templates and Pro tools.")

        _update_pro_tools_lock_state()
        license_unlock_button.clicked.connect(_update_pro_tools_lock_state)
        license_remove_button.clicked.connect(_update_pro_tools_lock_state)

        layout = text
        cleanup_checkbox = QCheckBox("Clean up filler words (\"um\", \"uh\", \"like\")")
        cleanup_checkbox.setChecked(hotkey_settings.get_cleanup_enabled())
        layout.addWidget(cleanup_checkbox)

        voice_commands_checkbox = QCheckBox("Voice commands (punctuation by voice)")
        voice_commands_checkbox.setChecked(hotkey_settings.get_voice_commands_enabled())
        layout.addWidget(voice_commands_checkbox)

        voice_commands_hint = QLabel(
            'Say these words while dictating and they\'ll be typed as punctuation '
            "instead of literal text -- e.g. \"period\", \"comma\", \"question mark\", "
            '"new line", "new paragraph", "open quote"/"close quote". Say '
            '"scratch that" alone to undo the last thing VoxScribe typed, '
            '"delete last word" to remove just the last word, or "delete '
            'last sentence" to remove just the last sentence. "Capitalize '
            'that", "all caps" and "lowercase that" change it, and "replace '
            'X with Y" swaps a word in it.'
        )
        voice_commands_hint.setObjectName("settingsHint")
        voice_commands_hint.setWordWrap(True)
        layout.addWidget(voice_commands_hint)

        send_it_checkbox = QCheckBox('Say "send it" to press Enter')
        send_it_checkbox.setChecked(hotkey_settings.get_send_it_enabled())
        layout.addWidget(send_it_checkbox)

        send_it_hint = QLabel(
            'Say "send it" on its own, or at the end of your message after a '
            'short pause ("see you at noon, send it"), to press Enter in the '
            'app you dictated into, for example to send a chat message. Off by '
            'default, because it can send a message you meant to read through '
            'first.'
        )
        send_it_hint.setObjectName("settingsHint")
        send_it_hint.setWordWrap(True)
        layout.addWidget(send_it_hint)

        layout = general
        sound_checkbox = QCheckBox("Play a sound when recording starts/stops")
        sound_checkbox.setChecked(hotkey_settings.get_sound_enabled())
        layout.addWidget(sound_checkbox)

        layout = audio
        typing_delay_label = QLabel("TYPING DELAY (MS PER CHARACTER)")
        typing_delay_label.setObjectName("settingsSectionLabel")
        layout.addWidget(typing_delay_label)

        typing_delay_spin = _NoWheelSpinBox()
        typing_delay_spin.setRange(
            hotkey_settings.MIN_TYPING_DELAY_MS, hotkey_settings.MAX_TYPING_DELAY_MS
        )
        typing_delay_spin.setValue(hotkey_settings.get_typing_delay_ms())
        typing_delay_spin.setSuffix(" ms")
        typing_delay_spin.setMinimumHeight(36)
        layout.addWidget(typing_delay_spin)

        typing_delay_hint = QLabel(
            "How long VoxScribe pauses between typed characters. The default of 30 works "
            "in most apps. Raise it if a rich-text editor or web chat box scrambles or "
            "drops characters; lower it if you want text to appear faster."
        )
        typing_delay_hint.setObjectName("settingsHint")
        typing_delay_hint.setWordWrap(True)
        layout.addWidget(typing_delay_hint)

        layout = privacy
        telemetry_checkbox = QCheckBox("Send an anonymous launch ping (app version and OS only)")
        telemetry_checkbox.setChecked(hotkey_settings.get_telemetry_enabled())
        layout.addWidget(telemetry_checkbox)

        telemetry_hint = QLabel(
            "One tiny ping each time VoxScribe starts, so I can see how many people use it. "
            "No audio, text, or personal data. Takes effect on the next launch."
        )
        telemetry_hint.setObjectName("settingsHint")
        telemetry_hint.setWordWrap(True)
        layout.addWidget(telemetry_hint)

        excluded_label = QLabel("DISABLED APPS")
        excluded_label.setObjectName("settingsSectionLabel")
        layout.addWidget(excluded_label)

        excluded_edit = QLineEdit()
        excluded_edit.setPlaceholderText("e.g. keepass.exe, bitwarden.exe")
        excluded_edit.setText(", ".join(hotkey_settings.get_excluded_apps()))
        excluded_edit.setMinimumHeight(36)
        layout.addWidget(excluded_edit)

        excluded_hint = QLabel(
            "VoxScribe won't record while one of these apps is focused, comma-"
            "separated executable names, e.g. a password manager."
        )
        excluded_hint.setObjectName("settingsHint")
        excluded_hint.setWordWrap(True)
        layout.addWidget(excluded_hint)

        layout = about
        stats_label = QLabel("STATISTICS")
        stats_label.setObjectName("settingsSectionLabel")
        layout.addWidget(stats_label)

        sessions, words = hotkey_settings.get_stats()
        stats_value = QLabel(
            f"{sessions:,} dictation{'s' if sessions != 1 else ''} · {words:,} words"
        )
        stats_value.setObjectName("settingsHint")
        layout.addWidget(stats_value)

        layout = general
        startup_label = QLabel("STARTUP")
        startup_label.setObjectName("settingsSectionLabel")
        layout.addWidget(startup_label)

        auto_start_checkbox = QCheckBox("Start VoxScribe automatically when Windows starts")
        auto_start_checkbox.setChecked(hotkey_settings.get_auto_start())
        layout.addWidget(auto_start_checkbox)

        layout = about
        version_label = QLabel("VERSION")
        version_label.setObjectName("settingsSectionLabel")
        layout.addWidget(version_label)
        version_value = QLabel(f"VoxScribe {__version__}")
        version_value.setObjectName("settingsHint")
        layout.addWidget(version_value)
        update_button = QPushButton("Check for updates")
        update_button.setObjectName("secondaryButton")
        update_button.setCursor(Qt.PointingHandCursor)
        update_button.clicked.connect(lambda: self._start_update_check(manual=True))
        layout.addWidget(update_button)

        def _apply() -> None:
            changes = []


            new_key = combo.currentData()
            if new_key != self._hotkey:
                self._hotkey = new_key
                hotkey_settings.set_hotkey(new_key)
                self._register_global_hotkey()
                changes.append(f"Hotkey changed to {new_key.upper()}.")

            new_talk_mode = talk_mode_combo.currentData()
            if new_talk_mode != current_talk_mode:
                hotkey_settings.set_talk_mode(new_talk_mode)
                changes.append(f"Talk mode set to: {talk_mode_combo.currentText()}")

            new_device = mic_combo.currentData()
            if new_device != current_device:
                hotkey_settings.set_input_device(new_device)
                changes.append(
                    "Microphone set to auto-detect."
                    if new_device is None
                    else f"Microphone set to {mic_combo.currentText()}."
                )

            new_keep_ready = keep_ready_checkbox.isChecked()
            if new_keep_ready != hotkey_settings.get_keep_mic_ready_enabled():
                hotkey_settings.set_keep_mic_ready_enabled(new_keep_ready)
                changes.append(
                    "Microphone will stay ready."
                    if new_keep_ready
                    else "Microphone ready mode off."
                )
            self._sync_ready_stream()

            new_language = language_combo.currentData()
            if new_language != current_language:
                hotkey_settings.set_language(new_language)
                self._refresh_language_badge()
                changes.append(f"Dictation language set to {language_combo.currentText()}.")

            new_translate_enabled = translate_checkbox.isChecked()
            if new_translate_enabled != hotkey_settings.get_translate_to_english_enabled():
                hotkey_settings.set_translate_to_english_enabled(new_translate_enabled)
                changes.append(
                    "Translate to English enabled."
                    if new_translate_enabled
                    else "Translate to English disabled."
                )

            new_model_size = model_combo.currentData()
            if new_model_size in hotkey_settings.PRO_MODEL_SIZES and not hotkey_license.is_pro():
                new_model_size = current_model_size
            if new_model_size != current_model_size:
                hotkey_settings.set_model_size(new_model_size)
                changes.append(
                    f"Whisper model set to {model_combo.currentText()} "
                    "(takes effect after restart)."
                )

            new_vocabulary = [t.strip() for t in vocab_edit.text().split(",") if t.strip()]
            if new_vocabulary != hotkey_settings.get_custom_vocabulary():
                hotkey_settings.set_custom_vocabulary(new_vocabulary)
                changes.append(
                    f"Custom vocabulary updated ({len(new_vocabulary)} term"
                    f"{'s' if len(new_vocabulary) != 1 else ''})."
                    if new_vocabulary
                    else "Custom vocabulary cleared."
                )

            new_replacements = replacements.parse_replacements_text(replacements_edit.toPlainText())
            new_mode = mode_combo.currentData()
            if new_mode in modes.PRO_MODES and not hotkey_license.is_pro():
                new_mode = modes.DEFAULT_MODE
            if new_mode != hotkey_settings.get_mode():
                hotkey_settings.set_mode(new_mode)
                changes.append(f"Dictation mode: {modes.MODE_LABELS[new_mode].split(' (')[0]}.")
            if hotkey_license.is_pro():
                new_auto_modes = auto_modes_checkbox.isChecked()
                if new_auto_modes != hotkey_settings.get_auto_modes_enabled():
                    hotkey_settings.set_auto_modes_enabled(new_auto_modes)
                    changes.append(
                        "Modes switch by app."
                        if new_auto_modes
                        else "Modes no longer switch by app."
                    )

            new_redo_key = redo_key_combo.currentData()
            if new_redo_key != hotkey_settings.get_redo_hotkey():
                hotkey_settings.set_redo_hotkey(new_redo_key)
                self._register_global_hotkey()
                changes.append(
                    f"Try harder key set to {new_redo_key.upper()}."
                    if new_redo_key
                    else "Try harder key off."
                )

            if new_replacements != replacements.get_replacements():
                replacements.set_replacements(new_replacements)
                changes.append(
                    f"Word replacements updated ({len(new_replacements)})."
                    if new_replacements
                    else "Word replacements cleared."
                )

            if hotkey_license.is_pro():
                new_snippets = []
                for line in snippets_edit.toPlainText().splitlines():
                    if "=>" not in line:
                        continue
                    trigger, _, expansion = line.partition("=>")
                    if trigger.strip():
                        new_snippets.append((trigger.strip(), expansion.strip()))
                if new_snippets != snippets.get_snippets():
                    snippets.set_snippets(new_snippets)
                    changes.append(
                        f"Snippets updated ({len(new_snippets)})."
                        if new_snippets
                        else "Snippets cleared."
                    )

            if hotkey_license.is_pro():
                new_templates = templates.parse_lines(templates_edit.toPlainText())
                if new_templates != templates.get_templates():
                    templates.set_templates(new_templates)
                    changes.append(
                        f"Templates updated ({len(new_templates)})."
                        if new_templates
                        else "Templates cleared."
                    )

                new_profiles = app_profiles.parse_lines(profiles_edit.toPlainText())
                if new_profiles != app_profiles.get_profiles():
                    app_profiles.set_profiles(new_profiles)
                    changes.append(
                        f"App profiles updated ({len(new_profiles)})."
                        if new_profiles
                        else "App profiles cleared."
                    )

                new_smart = smart_checkbox.isChecked()
                if new_smart != hotkey_settings.get_smart_formatting_enabled():
                    hotkey_settings.set_smart_formatting_enabled(new_smart)
                    changes.append("Smart formatting on." if new_smart else "Smart formatting off.")

                new_second_key = second_key_combo.currentData()
                new_second_language = second_language_combo.currentData()
                if (
                    new_second_key != hotkey_settings.get_second_hotkey()
                    or new_second_language != hotkey_settings.get_second_language()
                ):
                    hotkey_settings.set_second_hotkey(new_second_key)
                    hotkey_settings.set_second_language(new_second_language)
                    self._register_global_hotkey()
                    changes.append(
                        f"Second language key set to {new_second_key.upper()}."
                        if new_second_key
                        else "Second language key off."
                    )

                new_speaker_count = speaker_count_combo.currentData()
                new_speaker_names = [n.strip() for n in speaker_names_edit.text().split(",")]
                if new_speaker_names == [""]:
                    new_speaker_names = []
                if new_speaker_count != hotkey_settings.get_speaker_count():
                    hotkey_settings.set_speaker_count(new_speaker_count)
                    changes.append("Speaker count updated.")
                if new_speaker_names != hotkey_settings.get_speaker_names():
                    hotkey_settings.set_speaker_names(new_speaker_names)
                    changes.append("Speaker names updated.")

                new_code = code_checkbox.isChecked()
                if new_code != hotkey_settings.get_code_dictation_enabled():
                    hotkey_settings.set_code_dictation_enabled(new_code)
                    changes.append("Code dictation on." if new_code else "Code dictation off.")

                new_offline = offline_checkbox.isChecked()
                if new_offline != hotkey_settings.get_offline_mode_enabled():
                    hotkey_settings.set_offline_mode_enabled(new_offline)
                    network_guard.set_blocking(new_offline)
                    changes.append(
                        "Offline mode on: VoxScribe will not use the network."
                        if new_offline
                        else "Offline mode off."
                    )

            new_cleanup_enabled = cleanup_checkbox.isChecked()
            if new_cleanup_enabled != hotkey_settings.get_cleanup_enabled():
                hotkey_settings.set_cleanup_enabled(new_cleanup_enabled)
                changes.append(
                    "Filler-word cleanup enabled."
                    if new_cleanup_enabled
                    else "Filler-word cleanup disabled."
                )

            new_voice_commands_enabled = voice_commands_checkbox.isChecked()
            if new_voice_commands_enabled != hotkey_settings.get_voice_commands_enabled():
                hotkey_settings.set_voice_commands_enabled(new_voice_commands_enabled)
                changes.append(
                    "Voice commands enabled."
                    if new_voice_commands_enabled
                    else "Voice commands disabled."
                )

            new_send_it_enabled = send_it_checkbox.isChecked()
            if new_send_it_enabled != hotkey_settings.get_send_it_enabled():
                hotkey_settings.set_send_it_enabled(new_send_it_enabled)
                changes.append(
                    '"Send it" enabled.' if new_send_it_enabled else '"Send it" disabled.'
                )

            new_sound_enabled = sound_checkbox.isChecked()
            if new_sound_enabled != hotkey_settings.get_sound_enabled():
                hotkey_settings.set_sound_enabled(new_sound_enabled)
                changes.append(
                    "Recording sounds enabled."
                    if new_sound_enabled
                    else "Recording sounds disabled."
                )

            new_caption_chars = caption_spin.value()
            if 0 < new_caption_chars < hotkey_settings.MIN_CAPTION_LINE_CHARS:
                new_caption_chars = hotkey_settings.MIN_CAPTION_LINE_CHARS
            if new_caption_chars != hotkey_settings.get_caption_line_chars():
                hotkey_settings.set_caption_line_chars(new_caption_chars)
                changes.append(
                    "Caption splitting off."
                    if new_caption_chars == 0
                    else f"Caption lines capped at {new_caption_chars} characters."
                )

            new_typing_delay = typing_delay_spin.value()
            if new_typing_delay != hotkey_settings.get_typing_delay_ms():
                hotkey_settings.set_typing_delay_ms(new_typing_delay)
                changes.append(f"Typing delay set to {new_typing_delay} ms.")

            new_telemetry_enabled = telemetry_checkbox.isChecked()
            if new_telemetry_enabled != hotkey_settings.get_telemetry_enabled():
                hotkey_settings.set_telemetry_enabled(new_telemetry_enabled)
                changes.append(
                    "Launch ping enabled." if new_telemetry_enabled else "Launch ping disabled."
                )

            new_excluded_apps = [a.strip() for a in excluded_edit.text().split(",") if a.strip()]
            if [a.lower() for a in new_excluded_apps] != hotkey_settings.get_excluded_apps():
                hotkey_settings.set_excluded_apps(new_excluded_apps)
                changes.append(
                    f"Disabled apps updated ({len(new_excluded_apps)})."
                    if new_excluded_apps
                    else "Disabled apps list cleared."
                )

            new_auto_start = auto_start_checkbox.isChecked()
            if new_auto_start != hotkey_settings.get_auto_start():
                try:
                    hotkey_settings.set_auto_start(new_auto_start)
                    changes.append(
                        "VoxScribe will now start with Windows."
                        if new_auto_start
                        else "VoxScribe will no longer start with Windows."
                    )
                except OSError as exc:
                    changes.append(f"Couldn't update the startup setting: {exc}")

            if changes and self.tray_icon is not None:
                self._tray_notify(
                    "VoxScribe",
                    " ".join(changes),
                    QSystemTrayIcon.MessageIcon.Information,
                    4000,
                )

        # The page sits in the main window's stack and is rebuilt each time
        # Settings opens, so every control starts from the saved values.
        page_index = self._pages.addWidget(dialog)
        previous_index = self._pages.currentIndex()
        if previous_index == page_index:
            previous_index = 0

        def _close(accepted: bool) -> None:
            self._settings_close = None
            _stop_mic_test()
            if accepted:
                _apply()
            self._pages.removeWidget(dialog)
            dialog.deleteLater()
            self._settings_nav_button.setChecked(False)
            self._switch_page(previous_index)

        self._settings_close = _close
        cancel_button.clicked.connect(lambda: _close(False))
        save_button.clicked.connect(lambda: _close(True))
        for btn in self._nav_buttons.values():
            btn.setChecked(False)
        self._settings_nav_button.setChecked(True)
        self._pages.setCurrentIndex(page_index)

    # -- system tray ------------------------------------------------------

    def _announce_whats_new(self) -> None:
        """Shows a one-time tray balloon summarizing what changed, the first
        time VoxScribe runs after an update. Skipped on a brand-new install
        (last_seen_version is None) -- there's nothing to compare against,
        and a "what's new" balloon makes no sense before someone has used
        the app at all."""
        last_seen = hotkey_settings.get_last_seen_version()
        if last_seen is None:
            # A brand-new install: the app starts hidden in the tray, so show
            # the welcome with its short demo once, after start-up settles.
            QTimer.singleShot(900, self._show_welcome)
        if last_seen != __version__:
            if last_seen is not None:
                notes = whats_new_text(__version__)
                if notes and self.tray_icon is not None:
                    self._tray_notify(
                        f"VoxScribe {__version__}",
                        notes,
                        QSystemTrayIcon.MessageIcon.Information,
                        8000,
                    )
            hotkey_settings.set_last_seen_version(__version__)

    def _show_welcome(self) -> None:
        """The first-run welcome with its looping demo (app/welcome.py)."""
        if getattr(self, "_welcome", None) is not None:
            self._welcome.raise_()
            self._welcome.activateWindow()
            return
        dialog = WelcomeDialog(self._hotkey, SETTINGS_DIALOG_STYLESHEET)
        dialog.setWindowIcon(self.windowIcon())
        self._welcome = dialog

        def _closed(result: int) -> None:
            self._welcome = None
            dialog.deleteLater()
            if result == 2:
                self._show_and_raise()

        dialog.finished.connect(_closed)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _setup_tray_icon(self) -> None:
        """Adds a tray icon so the app can keep running (hotkey + indicator
        still work) after the main window is closed/hidden."""
        if not ICON_PATH.exists() or not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = None
            return

        self.tray_icon = QSystemTrayIcon(QIcon(str(ICON_PATH)), self)
        self.tray_icon.setToolTip("VoxScribe")

        menu = QMenu()
        menu.setStyleSheet(TRAY_MENU_STYLESHEET)
        show_action = QAction("Show Window", self)
        show_action.triggered.connect(self._show_and_raise)
        menu.addAction(show_action)

        settings_action = QAction("Settings...", self)
        settings_action.triggered.connect(self._open_settings_dialog)
        menu.addAction(settings_action)

        redo_action = QAction("Try harder on the last dictation", self)
        redo_action.triggered.connect(self._try_harder)
        menu.addAction(redo_action)

        welcome_action = QAction("How to use VoxScribe", self)
        welcome_action.triggered.connect(self._show_welcome)
        menu.addAction(welcome_action)

        # Hidden until an update is found, then stays in the menu (and the
        # tray tooltip changes) until it's acted on, so a missed 8-second
        # notification doesn't mean the update is never noticed.
        self._update_action = QAction("Update available", self)
        self._update_action.triggered.connect(self._on_tray_message_clicked)
        self._update_action.setVisible(False)
        menu.addAction(self._update_action)

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
        self.tray_icon.messageClicked.connect(self._on_tray_balloon_clicked)
        self.tray_icon.show()

        # The app now starts hidden (no window pops up on launch), so this
        # is the only cue that it's actually running -- and the only place
        # to tell the user the global hotkey didn't register, since that
        # failure happens before this tray icon even exists.
        if self._hotkey_registration_error:
            self._tray_notify(
                "VoxScribe",
                f"Couldn't register the {self._hotkey.upper()} hotkey (often needs "
                "admin rights). Open VoxScribe and use the Start/Stop button instead.",
                QSystemTrayIcon.MessageIcon.Warning,
                6000,
            )
        else:
            self._tray_notify(
                "VoxScribe",
                f"Running in the background. Hold {self._hotkey.upper()} anywhere to dictate.",
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
        quitting -- the hotkey and the floating indicator keep working in the
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

    def _refresh_update_action(self) -> None:
        """Keeps the tray menu's update item and tooltip in step with the
        update state: nothing, update found, or installer downloaded."""
        action = getattr(self, "_update_action", None)
        if action is None or self.tray_icon is None:
            return
        if self._downloaded_installer_path:
            action.setText("Run the downloaded update installer")
            action.setVisible(True)
            self.tray_icon.setToolTip("VoxScribe (update downloaded)")
        elif self._pending_update_info is not None:
            action.setText(f"Update to {self._pending_update_info.version} available")
            action.setVisible(True)
            self.tray_icon.setToolTip(
                f"VoxScribe (update {self._pending_update_info.version} available)"
            )
        else:
            action.setVisible(False)
            self.tray_icon.setToolTip("VoxScribe")

    def _on_update_found(self, info: UpdateInfo) -> None:
        self._pending_update_info = info
        self._downloaded_installer_path = None
        self._refresh_update_action()
        if self.tray_icon is None:
            return
        if info.asset_url:
            self._tray_notify_update(
                "VoxScribe update available",
                f"Version {info.version} is available (you're on {__version__}). "
                "Click this notification to download the installer.",
                QSystemTrayIcon.MessageIcon.Information,
                8000,
            )
        else:
            # No .exe asset found on the release (shouldn't normally
            # happen) -- fall back to the release page link, same as
            # before one-click download existed.
            self._tray_notify_update(
                "VoxScribe update available",
                f"Version {info.version} is available (you're on {__version__}). "
                "Click this notification to open the download page.",
                QSystemTrayIcon.MessageIcon.Information,
                8000,
            )

    def _on_update_none_found(self, manual: bool) -> None:
        if manual and self.tray_icon is not None:
            self._tray_notify(
                "VoxScribe",
                f"You're up to date (v{__version__}).",
                QSystemTrayIcon.MessageIcon.Information,
                4000,
            )

    def _on_update_check_failed(self, message: str, manual: bool) -> None:
        if manual and self.tray_icon is not None:
            self._tray_notify(
                "VoxScribe",
                f"Couldn't check for updates: {message}",
                QSystemTrayIcon.MessageIcon.Warning,
                5000,
            )

    def _show_balloon(self, title, message, icon, msecs, action=None) -> None:  # noqa: ANN001
        # `action` is what a click on this specific balloon does. Remembered
        # per balloon so a click can never trigger the action of an older one.
        self._balloon_action = action
        self.tray_icon.showMessage(title, message, icon, msecs)

    def _tray_notify(self, title, message, icon, msecs) -> None:  # noqa: ANN001
        """A balloon whose click does nothing. In particular it must never
        start an update download or run an installer."""
        self._show_balloon(title, message, icon, msecs)

    def _tray_notify_update(self, title, message, icon, msecs) -> None:  # noqa: ANN001
        """A balloon whose click acts on the pending update."""
        self._show_balloon(title, message, icon, msecs, self._on_tray_message_clicked)

    def _on_tray_balloon_clicked(self) -> None:
        action = self._balloon_action
        self._balloon_action = None
        if action is not None:
            action()

    def _copy_held_text(self) -> None:
        if self._held_text:
            QApplication.clipboard().setText(self._held_text)
            self._held_text = None
            self._set_status("Copied the held text to the clipboard", "ready")

    def _on_tray_message_clicked(self) -> None:
        # Three possible states, checked in order: a downloaded installer
        # ready to run, a download in progress (ignore the click), or an
        # update just found (start the download, or fall back to the
        # browser if the release has no .exe asset).
        if self._downloaded_installer_path:
            os.startfile(self._downloaded_installer_path)  # noqa: S606 -- Windows-only app
            self._downloaded_installer_path = None
            self._pending_update_info = None
            self._refresh_update_action()
            return

        if self._update_downloader is not None and self._update_downloader.isRunning():
            return

        info = self._pending_update_info
        if info is None:
            return

        if not info.asset_url or not info.asset_name:
            webbrowser.open(info.url)
            self._pending_update_info = None
            self._refresh_update_action()
            return

        if self.tray_icon is not None:
            self._tray_notify(
                "VoxScribe",
                "Downloading the update...",
                QSystemTrayIcon.MessageIcon.Information,
                4000,
            )
        self._update_downloader = UpdateDownloadThread(
            info.asset_url, info.asset_name, info.asset_sha256
        )
        self._update_downloader.done.connect(self._on_update_downloaded)
        self._update_downloader.failed.connect(self._on_update_download_failed)
        self._update_downloader.start()

    def _on_update_downloaded(self, path: str) -> None:
        self._downloaded_installer_path = path
        self._refresh_update_action()
        if self.tray_icon is not None:
            self._tray_notify_update(
                "VoxScribe update downloaded",
                "Click this notification to run the installer.",
                QSystemTrayIcon.MessageIcon.Information,
                8000,
            )

    def _on_update_download_failed(self, message: str) -> None:
        # Fall back to the release page rather than leaving the user stuck --
        # the next click opens it in the browser instead of retrying.
        info = self._pending_update_info
        self._pending_update_info = (
            UpdateInfo(version=info.version, url=info.url) if info else None
        )
        self._refresh_update_action()
        if self.tray_icon is not None:
            self._tray_notify_update(
                "VoxScribe",
                f"Couldn't download the update: {message}. "
                "Click this notification to open the download page instead.",
                QSystemTrayIcon.MessageIcon.Warning,
                6000,
            )

    def _open_logs_folder(self) -> None:
        CRASH_LOG_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(str(CRASH_LOG_DIR))  # noqa: S606 -- Windows-only app

    def _quit_app(self) -> None:
        try:
            keyboard.unhook_all()
        except Exception:  # noqa: BLE001
            pass
        if self._ready_stream is not None:
            try:
                self._ready_stream.stop()
                self._ready_stream.close()
            except Exception:  # noqa: BLE001
                pass
            self._ready_stream = None
        if getattr(self, "tray_icon", None) is not None:
            self.tray_icon.hide()
        self._indicator.close()
        QApplication.instance().quit()

    # -- status helpers -----------------------------------------------

    def _set_status(self, text: str, kind: str) -> None:
        self.status_pill.set_status(text, kind)

    def _set_record_button_recording(self, is_recording: bool) -> None:
        """Flips the record button's `recording` dynamic property, which the
        QSS in MAIN_STYLESHEET uses to swap it from accent-violet (idle) to
        green (actively recording) -- a clear at-a-glance state cue on top
        of the button's own text/icon change. Also swaps the mic/stop icon
        and switches the button's glow from violet to green, pulsing while
        the recording is live so the primary action visibly reads as "on".
        """
        self.record_button.setProperty("recording", is_recording)
        self.record_button.style().unpolish(self.record_button)
        self.record_button.style().polish(self.record_button)
        self.record_button.setIcon(self._stop_icon if is_recording else self._mic_icon)

        if is_recording:
            self._record_shadow.setColor(QColor(62, 207, 142, 130))
            self._record_pulse.start()
        else:
            self._record_pulse.stop()
            self._record_shadow.setColor(QColor(62, 207, 142, 110))
            self._record_shadow.setBlurRadius(24)

    def _update_save_button(self) -> None:
        has_text = bool(self.transcript_area.toPlainText().strip())
        self.save_button.setEnabled(has_text)
        self.copy_button.setEnabled(has_text)
        self.clear_button.setEnabled(has_text)

        self.transcript_area.setProperty("hasContent", has_text)
        self.transcript_area.style().unpolish(self.transcript_area)
        self.transcript_area.style().polish(self.transcript_area)

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

    def _start_model_load(self) -> None:
        self._model_failed = False
        # What will really be loaded (a size change in Settings only applies
        # after a restart); Try harder compares against this, not the setting.
        size = hotkey_settings.get_model_size()
        if size in hotkey_settings.PRO_MODEL_SIZES and not hotkey_license.is_pro():
            size = hotkey_settings.DEFAULT_MODEL_SIZE
        self._loaded_model_size = size
        animate_progress(self._model_progress, 0)
        self._loader = ModelLoaderThread()
        self._loader.done.connect(self._on_model_loaded)
        self._loader.failed.connect(self._on_model_load_failed)
        self._loader.progress.connect(lambda text: self._set_status(text, "transcribing"))
        self._loader.download.connect(self._on_model_download)
        self._loader.start()

    def _on_model_download(self, mb: int, expected_mb: int) -> None:
        self._model_progress.show()
        # Reports arrive once a second, so glide over about that long.
        animate_progress(self._model_progress, min(100, mb * 100 // expected_mb), 950)

    def _on_model_loaded(self, transcriber: Transcriber) -> None:
        self._model_progress.hide()
        self.transcriber = transcriber
        self._model_failed = False
        self.record_button.setText("Start Recording")
        self._set_status("Ready", "ready")
        self.record_button.setEnabled(True)
        self._set_import_enabled(True)

    def _on_model_load_failed(self, message: str) -> None:
        self._model_progress.hide()
        self._model_failed = True
        self._set_status("Model failed to load. Click Retry.", "error")
        self.transcript_area.append(
            "[error] The speech model could not be loaded: "
            f"{message}\nVoxScribe already tried to repair its download once. "
            "Check your internet connection and free disk space, then click "
            "Retry. If antivirus is removing model files, allow VoxScribe and "
            "the folder .cache\\huggingface in your user folder."
        )
        self.record_button.setText("Retry loading model")
        self.record_button.setEnabled(True)

    # -- recording / transcription --------------------------------------

    def toggle_recording(self) -> None:
        if self.transcriber is None and self._model_failed:
            self.record_button.setEnabled(False)
            self.record_button.setText("Start Recording")
            self._set_status("Loading model...", "loading")
            self._start_model_load()
            return
        if self.stream is None:
            self._start_recording()
        else:
            self._stop_recording()

    # -- hold-to-talk hotkey handlers ------------------------------------

    def _handle_primary_press(self) -> None:
        if not self._hotkey_key_down:
            self._language_override = None
        self._handle_hotkey_press()

    def _handle_alt_press(self) -> None:
        """Pro: the second key dictates in its own language."""
        if not self._hotkey_key_down:
            self._language_override = (hotkey_settings.get_second_language(),)
        self._handle_hotkey_press()

    def _handle_hotkey_press(self) -> None:
        if self._hotkey_key_down:
            # Key-repeat guard: holding a key down can fire repeated
            # "press" events on some systems -- ignore all but the first
            # until a release is seen.
            return
        self._hotkey_key_down = True
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
            if self._model_failed:
                self._indicator.flash_error("Model failed to load", 2500)
            else:
                self._indicator.flash_error("Still loading model...", 1500)
            return
        if self._import_active():
            # A file import is using the model; dictating now would run two
            # transcriptions at once and re-enable buttons mid-import.
            self._indicator.flash_error("Busy with file import", 1500)
            return
        if hotkey_settings.get_talk_mode() == "toggle":
            # Toggle mode: a press either starts or stops -- release (below)
            # does nothing. Still only stops a recording the hotkey itself
            # started, same guard as hold mode, so the hotkey can't steal
            # control from a recording the on-screen button started.
            if self.stream is not None and self._hotkey_active_session:
                self._hotkey_active_session = False
                self._stop_recording()
            elif self.stream is None and not transcribing:
                self._hotkey_active_session = True
                self._start_recording()
            return

        if self.stream is None and not transcribing:
            self._hotkey_active_session = True
            self._start_recording()

    def _handle_hotkey_release(self) -> None:
        self._hotkey_key_down = False
        if hotkey_settings.get_talk_mode() == "toggle":
            return
        if self._hotkey_active_session and self.stream is not None:
            self._hotkey_active_session = False
            self._stop_recording()

    def _set_import_enabled(self, enabled: bool) -> None:
        self.import_button.setEnabled(enabled)
        self.import_folder_button.setEnabled(enabled)

    def _import_active(self) -> bool:
        worker = getattr(self, "_file_worker", None)
        return bool(self._import_queue) or (worker is not None and worker.isRunning())

    def _start_recording(self) -> None:
        if self._import_active():
            return
        excluded_process = foreground_process_name()
        if excluded_process and excluded_process in hotkey_settings.get_excluded_apps():
            self._hotkey_active_session = False
            self._set_status(f"Dictation disabled for {excluded_process}", "error")
            self._indicator.flash_error("Dictation is off in this app")
            return

        # A new dictation starts: the previous one can no longer be redone.
        self._clear_redo()
        # The dictation mode for this app (core/modes.py), with any per-app
        # profile options on top (Pro).
        self._recording_mode, self._recording_profile = modes.effective_options(
            excluded_process,
            app_profiles.profile_for(excluded_process),
            hotkey_settings.get_mode(),
            hotkey_settings.get_auto_modes_enabled(),
            hotkey_license.is_pro(),
        )
        self._chunks = []
        # Falls back to auto-detection if the user's chosen device (Settings
        # -> Microphone) has been unplugged/disconnected since it was picked.
        device = resolve_input_device(hotkey_settings.get_input_device())

        if (
            self._ready_stream is not None
            and self._ready_buffer is not None
            and device == self._ready_device
        ):
            # Keep-ready mode: the stream is already open, so start from the
            # last fraction of a second it already heard.
            self._record_rate = self._ready_rate
            self._chunks = self._ready_buffer.drain()
            self._capturing = True
            self.stream = self._ready_stream
            self.record_button.setText("Stop Recording")
            self._set_record_button_recording(True)
            self._set_import_enabled(False)
            self._set_status("Recording...", "recording")
            self._indicator.show_status("recording", self._mode_badge())
            _play_start_sound()
            return

        # Record at the device's own native rate rather than forcing 16kHz --
        # some devices/drivers (e.g. a laptop's internal mic falling back to
        # when a Bluetooth headset isn't connected) reject a forced 16kHz
        # request outright. Resample down to 16kHz for Whisper after capture.
        self._record_rate = device_native_samplerate(device)

        def callback(indata, frames, time_info, status):  # noqa: ANN001
            chunk = indata[:, 0].copy()
            self._chunks.append(chunk)
            self._indicator.feed_audio(chunk)

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
            self._indicator.flash_error("No microphone available")
            return
        self.record_button.setText("Stop Recording")
        self._set_record_button_recording(True)
        self._set_import_enabled(False)
        self._set_status("Recording...", "recording")
        self._indicator.show_status("recording", self._mode_badge())
        _play_start_sound()

    def _stop_recording(self) -> None:
        # Capture now, while the user is still (presumably) looking at the
        # window they were dictating into -- transcription hasn't started
        # yet, so this is the closest we get to "the window they meant".
        self._recording_target_hwnd = foreground_window_handle()

        if self.stream is self._ready_stream:
            self._capturing = False
        else:
            # The device can vanish mid-recording (Bluetooth drop); a failure
            # here must not leave the stream set and the window stuck on
            # "Recording...".
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:  # noqa: BLE001
                pass
        self.stream = None
        self._hotkey_active_session = False
        _play_stop_sound()

        self.record_button.setEnabled(False)
        self.record_button.setText("Start Recording")
        self._set_record_button_recording(False)
        self._set_status("Transcribing...", "transcribing")
        self._indicator.show_status("transcribing")

        audio = np.concatenate(self._chunks) if self._chunks else np.zeros(0, dtype=np.float32)
        audio = resample_to_16k(audio, self._record_rate)
        self._chunks = []
        self._last_recording_duration = len(audio) / SAMPLE_RATE

        params = (
            self._effective_language(),
            hotkey_settings.custom_vocabulary_prompt(),
            "translate" if hotkey_settings.get_translate_to_english_enabled() else "transcribe",
        )
        # Kept in memory only, for Try harder; dropped once the text is typed
        # and the redo window passes (core/redo.py).
        self._last_audio = audio
        self._last_audio_params = params
        self._worker = TranscribeThread(self.transcriber, audio, *params)
        self._language_override = None
        self._worker.done.connect(self._on_transcribed)
        self._worker.failed.connect(self._on_transcribe_failed)
        self._worker.start()

    def _mode_badge(self) -> str:
        """The mode's name for the recording pill, or "" for the default mode."""
        mode = getattr(self, "_recording_mode", modes.DEFAULT_MODE)
        return "" if mode == modes.DEFAULT_MODE else modes.MODE_LABELS[mode].split(" (")[0]

    def _effective_language(self) -> str | None:
        """The second key's language, else the focused app's profile, else Settings."""
        if self._language_override is not None:
            return self._language_override[0]
        if "language" in self._recording_profile:
            return self._recording_profile["language"]  # type: ignore[return-value]
        return hotkey_settings.get_language()

    def _transcript_context_menu(self, pos) -> None:
        """Right-click in the transcript: besides Copy and Select all, offer to
        always correct the selected words. It only ever reads the transcript
        VoxScribe already shows, never another app."""
        menu = self.transcript_area.createStandardContextMenu()
        heard = replacements.clean_selection(self.transcript_area.textCursor().selectedText())
        if heard:
            shown = heard if len(heard) <= 30 else heard[:29] + "..."
            menu.addSeparator()
            action = menu.addAction(f'Always correct "{shown}"...')
            action.triggered.connect(lambda: self._add_correction(heard))
        menu.exec(self.transcript_area.mapToGlobal(pos))
        menu.deleteLater()

    def _add_correction(self, heard: str) -> None:
        replacement, accepted = QInputDialog.getText(
            self,
            "Always correct this word",
            f'Whenever VoxScribe hears "{heard}", type this instead:',
        )
        if not accepted:
            return
        status = replacements.add_replacement(heard, replacement)
        if status in ("added", "updated"):
            self._set_status(f'Will type "{replacement.strip()}" instead of "{heard}"', "ready")
        elif status == "unchanged":
            self._set_status("That correction is already saved", "ready")
        else:
            self._set_status("Type what it should be instead", "error")

    def _option(self, name: str, default: bool) -> bool:
        """A setting as the focused app's profile sees it."""
        return bool(self._recording_profile.get(name, default))

    def _on_transcribed(self, text: str) -> None:
        self._send_after_typing = False
        voice_commands_on = self._option(
            "voice_commands", hotkey_settings.get_voice_commands_enabled()
        )
        editing_mode = get_editing_command(text) if text else None
        if editing_mode and voice_commands_on:
            self._after_typing(lambda: self._handle_editing_command(editing_mode))
            return
        if text and voice_commands_on:
            transform = get_transform_command(text)
            if transform:
                self._after_typing(
                    lambda: self._handle_rewrite_command(
                        lambda old: apply_transform(old, transform), "Changed last dictation"
                    )
                )
                return
            swap = get_replace_command(text)
            # "replace the battery with a new one" is ordinary speech unless
            # the last dictation really contains the first part. A dictation
            # still being typed counts as the last one, so wait for it first.
            if swap and self._typing_lock.locked():
                self._after_typing(lambda: self._on_transcribed(text))
                return
            if (
                swap
                and self._last_typed_text
                and apply_replace(self._last_typed_text, *swap) is not None
            ):
                self._after_typing(
                    lambda: self._handle_rewrite_command(
                        lambda old: apply_replace(old, *swap), "Replaced in last dictation"
                    )
                )
                return
        if text and hotkey_settings.get_send_it_enabled() and is_send_command(text):
            self._after_typing(self._handle_send_command)
            return
        # "how are you? send it": type the sentence, then press Enter.
        if text and hotkey_settings.get_send_it_enabled():
            sentence = split_trailing_send(text)
            if sentence is not None:
                text = sentence
                self._send_after_typing = True

        # "meet me at noon, replace noon with one": a replace at the end of the same sentence.
        if text and voice_commands_on:
            swapped = apply_trailing_replace(text)
            if swapped is not None:
                text = swapped
        # "bring the notes, all caps": a command at the end of the same sentence.
        trailing_mode = None
        if text and voice_commands_on:
            split = split_trailing_transform(text)
            if split:
                text, trailing_mode = split

        pro = hotkey_license.is_pro()
        if text and pro and self._handle_template_turn(text):
            return

        text = self._finish_formatting(text, pro, voice_commands_on, trailing_mode)
        self._deliver_text(text)

    def _finish_formatting(
        self, text: str, pro: bool, voice_commands_on: bool, trailing_mode: str | None
    ) -> str:
        """Code dictation or cleanup, spoken punctuation, smart formatting,
        replacements, snippets and a trailing "all caps"-style command. Shared
        by normal dictation and Try harder, so a redo is formatted the same."""
        if text and pro and self._option("code", hotkey_settings.get_code_dictation_enabled()):
            # Code is not prose: no capitalizing, no full stops, no filler cleanup.
            text = code_dictation.to_code(text)
        else:
            if text and self._option("cleanup", hotkey_settings.get_cleanup_enabled()):
                text = clean_transcript(text)
            if text and voice_commands_on:
                text = apply_voice_commands(text)
            smart_on = self._option("smart", hotkey_settings.get_smart_formatting_enabled())
            if text and pro and smart_on:
                text = smart_format.smart_format(text)
            if text and self._option("period", True) is False:
                # Chat mode: no full stop at the end of a one-sentence message.
                text = modes.drop_final_period(text)
        if text:
            text = replacements.apply_replacements(text)
        if text and pro:
            text = snippets.expand_snippet(text)
        if text and trailing_mode:
            text = apply_transform(text, trailing_mode)
        return text

    # -- Try harder (core/redo.py) ------------------------------------------

    def _on_redo_key(self, event) -> bool:  # noqa: ANN001
        """Runs on the keyboard hook's thread. Takes the key only while a redo
        is possible; the rest of the time it reaches the app as usual."""
        if not self._redo_armed and not self._redo_key_down:
            if (
                event.event_type == "down"
                and 0 < time.monotonic() - self._last_typed_at < LATE_HINT_SEC
            ):
                # Too late to redo: let the key through, but say why nothing
                # happens instead of failing silently.
                self._hotkey_bridge.redo_too_late.emit()
            return True
        if event.event_type == "down":
            if not self._redo_key_down:
                self._redo_key_down = True
                self._hotkey_bridge.redo_requested.emit()
            return False
        self._redo_key_down = False
        return False

    def _redo_too_late(self) -> None:
        if self._indicator.isVisible():
            return
        key = hotkey_settings.get_redo_hotkey().upper()
        self._indicator.flash_error(
            f"Too late to redo. Press {key} within {REDO_WINDOW_SEC // 60} min of dictating", 3000
        )

    def _set_redo(self, redo: dict | None) -> None:
        self._redo = redo
        self._redo_armed = redo is not None
        if redo is None:
            self._redo_expiry_timer.stop()
        else:
            self._redo_expiry_timer.start(REDO_WINDOW_SEC * 1000)

    def _clear_redo(self) -> None:
        self._set_redo(None)
        self._last_audio = None

    def _try_harder(self) -> None:
        redo = self._redo
        if redo is None or time.monotonic() - redo["at"] > REDO_WINDOW_SEC:
            self._clear_redo()
            self._indicator.flash_error("Nothing to redo")
            return
        if self._redo_worker is not None and self._redo_worker.isRunning():
            return
        if foreground_window_handle() != redo["hwnd"] or self._last_typed_text != redo["typed"]:
            self._clear_redo()
            self._indicator.flash_error("Can't redo, the text or window changed")
            return
        downloaded = {
            size for size, _ in hotkey_settings.AVAILABLE_MODEL_SIZES if is_model_downloaded(size)
        }
        current = self._loaded_model_size
        size, bigger = pick_redo_model(current, hotkey_license.is_pro(), downloaded)
        if not bigger:
            # No bigger model to use: the model already loaded runs again in
            # careful mode (core/redo.py), so nothing new has to load.
            cached = (current, self.transcriber) if self.transcriber is not None else None
        else:
            cached = (
                self._redo_model if self._redo_model and self._redo_model[0] == size else None
            )
        language, prompt, task = redo["params"]
        self._indicator.show_status("redo")
        self._set_status("Trying harder...", "transcribing")
        worker = TranscribeThread(
            cached[1] if cached else None,
            redo["audio"],
            language,
            prompt,
            task,
            beam_size=CAREFUL_BEAM_SIZE,
            load_size=None if cached else size,
        )
        worker.loaded.connect(lambda model: setattr(self, "_redo_model", (size, model)))
        worker.done.connect(lambda text: self._on_redo_done(redo, size, text, bigger))
        worker.failed.connect(self._on_redo_failed)
        self._redo_worker = worker
        worker.start()

    def _on_redo_done(self, redo: dict, size: str, raw: str, bigger: bool = True) -> None:
        self._redo_model_timer.start(5 * 60 * 1000)
        if self._redo is not redo:
            # A new dictation started meanwhile; this result is stale.
            return
        saved_profile = self._recording_profile
        self._recording_profile = redo["profile"]
        try:
            voice_commands_on = self._option(
                "voice_commands", hotkey_settings.get_voice_commands_enabled()
            )
            text = raw
            if text and hotkey_settings.get_send_it_enabled():
                text = split_trailing_send(text) or text
            if text and voice_commands_on:
                text = apply_trailing_replace(text) or text
            trailing_mode = None
            if text and voice_commands_on:
                split = split_trailing_transform(text)
                if split:
                    text, trailing_mode = split
            new = self._finish_formatting(
                text, hotkey_license.is_pro(), voice_commands_on, trailing_mode
            )
        finally:
            self._recording_profile = saved_profile

        old = redo["typed"]
        name = next(
            (n for s, n in hotkey_settings.AVAILABLE_MODEL_SIZES if s == size), size
        ).split(":", 1)[-1].split(",")[0].strip()
        if not bigger:
            name += ", careful mode"
        self._clear_redo()
        if not new or new == old:
            self._set_status("Try harder found the same words", "ready")
            self._indicator.flash_success("Same result")
            return
        if foreground_window_handle() != redo["hwnd"] or self._last_typed_text != old:
            self._set_status("Try harder: the text or window changed", "error")
            self._indicator.flash_error("Can't redo, the text or window changed")
            return
        backspaces, to_type = compute_rewrite(old, new)
        typing_delay = hotkey_settings.get_typing_delay_ms() / 1000
        self._last_typed_text = new

        def _retype() -> None:
            with self._typing_lock:
                try:
                    for _ in range(backspaces):
                        keyboard.send("backspace")
                    if to_type:
                        keyboard.write(to_type, delay=typing_delay)
                except Exception:  # noqa: BLE001
                    pass

        threading.Thread(target=_retype, daemon=True).start()
        history.replace_last_text(old, new)
        self._refresh_history_feed()
        self.transcript_area.append(f"[tried harder with {name}] {new}")
        self._set_status(f"Retyped with {name}", "ready")
        self._indicator.flash_success(f"Fixed with {name}", 1400)

    def _on_redo_failed(self, message: str) -> None:
        self._set_status(f"Try harder failed: {message}", "error")
        self._indicator.flash_error("Try harder failed")

    # How long a half-filled template waits for the next answer before it is dropped.
    _TEMPLATE_TIMEOUT_SEC = 120

    def _handle_template_turn(self, text: str) -> bool:
        """Pro. Starts a spoken template, or takes the next answer for one in
        progress. Returns True when the utterance was consumed by a template."""
        session = self._template_session
        if session is not None or templates.find_template(text, templates.get_templates()):
            # A template's text is built from several answers; redoing only
            # the last recording would replace all of it with one answer.
            self._last_audio = None
        if session is not None and time.monotonic() - self._template_last_turn > (
            self._TEMPLATE_TIMEOUT_SEC
        ):
            session = self._template_session = None

        if session is None:
            template = templates.find_template(text, templates.get_templates())
            if template is None:
                return False
            session = templates.TemplateSession(template)
            if session.finished:
                self._deliver_text(session.result())
                return True
            self._template_session = session
        elif session.feed(text) == "cancel":
            self._template_session = None
            self._deliver_text("")
            self._indicator.hide_indicator()
            self._set_status("Template cancelled", "ready")
            return True

        self._template_last_turn = time.monotonic()
        if session.finished:
            self._template_session = None
            self._deliver_text(session.result())
            return True

        prompt = session.prompt or ""
        self.record_button.setEnabled(True)
        self._set_import_enabled(True)
        self._set_status(f'Template "{session.name}": say {prompt}', "ready")
        self._indicator.show_status(f"Say: {prompt[:14]}")
        return True

    def _deliver_text(self, text: str) -> None:
        """Shows the finished text and types it into the focused window."""
        self.record_button.setEnabled(True)
        self._set_import_enabled(True)

        if text and focused_is_password():
            # Never type dictation into a password box, and keep what was said
            # out of the transcript and history too. Checked again after
            # refocusing, in _type_into_focused_window.
            self.transcript_area.append("[not typed: password field]")
            self._set_status("Not typed: the box is a password field", "error")
            self._indicator.flash_error("Not typing into a password field", 2500)
            return

        self.transcript_area.append(text if text else "[no speech recognized]")

        if text:
            # The pill stays on "Transcribing" until the text is really typed
            # (or held): _type_into_focused_window shows the check or the error.
            hotkey_settings.record_dictation(len(text.split()))
            history.add_entry(text, self._last_recording_duration)
            self._refresh_history_feed()
            # Simulate typing directly into whatever window currently has
            # focus (not necessarily this app -- that's the point of the
            # global hotkey). This deliberately does NOT touch the
            # clipboard, so it won't clobber anything the user has copied.
            QTimer.singleShot(150, lambda: self._type_into_focused_window(text))
            self._set_status("Typed into active window", "ready")
        else:
            self._set_status("Ready", "ready")
            # Usually a mic that is too quiet or muted: say so instead of
            # silently vanishing.
            self._indicator.flash_error("No speech heard")

    def _open_connection_log(self, parent: QWidget) -> None:
        """Shows every outside connection VoxScribe has tried, newest first."""
        log_dialog = QDialog(parent)
        log_dialog.setWindowTitle("Connection log")
        log_dialog.setStyleSheet(SETTINGS_DIALOG_STYLESHEET)
        log_dialog.resize(520, 360)
        log_layout = QVBoxLayout(log_dialog)

        view = QTextEdit()
        view.setReadOnly(True)
        log_layout.addWidget(view)

        def refresh() -> None:
            entries = network_guard.recent(200)
            view.setPlainText(
                "\n".join(
                    f"{datetime.fromtimestamp(e.when):%Y-%m-%d %H:%M:%S}  "
                    f"{'BLOCKED' if e.blocked else 'allowed'}  {e.host}"
                    for e in entries
                )
                or "No outside connections have been made."
            )

        refresh()
        buttons = QHBoxLayout()
        clear_button = QPushButton("Clear log")
        close_button = QPushButton("Close")
        clear_button.setObjectName("ghostButton")
        close_button.setObjectName("secondaryButton")
        for button in (clear_button, close_button):
            button.setCursor(Qt.PointingHandCursor)
        buttons.addWidget(clear_button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)
        log_layout.addLayout(buttons)
        clear_button.clicked.connect(lambda: (network_guard.clear_log(), refresh()))
        close_button.clicked.connect(log_dialog.accept)
        log_dialog.exec()

    def _switch_page(self, index: int) -> None:
        if getattr(self, "_settings_close", None) is not None:
            # Leaving an open Settings page through the sidebar discards it.
            self._settings_close(False)
        self._pages.setCurrentIndex(index)
        for i, btn in self._nav_buttons.items():
            btn.setChecked(i == index)
        if index == 1:
            self._refresh_insights(from_zero=True)

    def _build_insights_page(self) -> None:
        self._insights_page = InsightsPage()
        self._pages.addWidget(self._insights_page)

    def _refresh_insights(self, from_zero: bool = False) -> None:
        """Opening the page counts everything up from zero; a new dictation
        counts up from the old numbers."""
        self._insights_page.refresh(animate=from_zero)

    def _refresh_history_feed(self) -> None:
        """Rebuilds the Dictation page's "Today" feed from core/history.py,
        and refreshes the Insights stat cards alongside it since both derive
        from the same underlying data."""
        while self._history_feed_layout.count() > 1:  # keep the trailing stretch
            item = self._history_feed_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        entries = history.get_today(limit=20)
        if not entries:
            empty = QLabel("No dictations yet today.")
            empty.setObjectName("historyEmpty")
            self._history_feed_layout.insertWidget(0, empty)
        else:
            newest = (entries[0].timestamp, entries[0].text)
            # The first build at startup has nothing "new" to fade in.
            previous_top = getattr(self, "_last_feed_top", newest)
            for entry in entries:
                row = QWidget()
                row.setObjectName("historyItem")
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(8, 6, 8, 6)
                row_layout.setSpacing(10)

                time_label = QLabel(entry.local_datetime().strftime("%I:%M %p").lstrip("0"))
                time_label.setObjectName("historyTime")
                time_label.setFixedWidth(64)
                row_layout.addWidget(time_label)

                text_label = QLabel(entry.text)
                text_label.setObjectName("historyText")
                text_label.setWordWrap(True)
                row_layout.addWidget(text_label, stretch=1)

                self._history_feed_layout.insertWidget(self._history_feed_layout.count() - 1, row)
                if entry is entries[0] and newest != previous_top:
                    # Only the dictation that just arrived fades in, not the
                    # whole list every time it is rebuilt.
                    fade_in(row)
            self._last_feed_top = newest

        self._refresh_insights()

    @staticmethod
    def _wait_for_foreground(hwnd: int, timeout: float = 0.3) -> bool:
        """SetForegroundWindow can take a moment to actually change the
        foreground window, so poll briefly before deciding it failed."""
        deadline = time.monotonic() + timeout
        while foreground_window_handle() != hwnd:
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.02)
        return True

    def _hold_text(self, text: str) -> None:
        self._held_text = text
        self._set_status("Text not typed: the original window changed", "error")
        self._indicator.flash_error("Window changed, text held", 3000)
        if self.tray_icon is not None:
            self._show_balloon(
                "VoxScribe held your text",
                "The window you dictated into changed, so nothing was typed. "
                "Click here to copy the text.",
                QSystemTrayIcon.MessageIcon.Warning,
                8000,
                self._copy_held_text,
            )

    def _type_into_focused_window(self, text: str) -> None:
        # Transcription runs in the background and finishes after a delay --
        # long enough for the user to have switched to a different window
        # since they stopped recording. Re-focus the window captured at
        # _stop_recording() so the text lands where they meant it to, not
        # wherever they've since clicked. If that fails (window closed,
        # Windows refuses the focus change -- see focus_window()'s
        # docstring), don't type anywhere: see _hold_text().
        target_hwnd = self._recording_target_hwnd
        # Taken now, so text that is held instead of typed never sends anything.
        send_after = self._send_after_typing
        self._send_after_typing = False
        if target_hwnd is not None:
            focus_window(target_hwnd)
            if not self._wait_for_foreground(target_hwnd):
                # The window the user dictated into is gone or won't take
                # focus back. Typing now would put the text into whatever
                # else is focused (possibly a chat or another private
                # field), so hold it instead. The text is already in the
                # transcript and history; clicking the balloon copies it.
                self._hold_text(text)
                return
        if focused_is_password():
            self._set_status("Not typed: the box is a password field", "error")
            self._indicator.flash_error("Not typing into a password field", 2500)
            return
        self._last_typed_at = time.monotonic()
        redo_key = hotkey_settings.get_redo_hotkey()
        hints_left = TYPED_HINT_COUNT - hotkey_settings.get_redo_hints_shown()
        if redo_key and hints_left > 0 and not send_after:
            hotkey_settings.set_redo_hints_shown(TYPED_HINT_COUNT - hints_left + 1)
            self._indicator.flash_success(f"Typed. {redo_key.upper()} to try harder", 1800)
        else:
            self._indicator.flash_success("Typed")
        if not send_after and self._last_audio is not None:
            # Try harder can now redo this dictation for REDO_WINDOW_SEC.
            self._set_redo(
                {
                    "audio": self._last_audio,
                    "params": self._last_audio_params,
                    "profile": self._recording_profile,
                    "typed": text,
                    "hwnd": target_hwnd if target_hwnd is not None else foreground_window_handle(),
                    "at": time.monotonic(),
                }
            )
        else:
            self._clear_redo()
        typing_delay = hotkey_settings.get_typing_delay_ms() / 1000

        def _type() -> None:
            # Typed on a background thread: at 30ms per character a long
            # dictation would otherwise freeze the window and tray for as
            # long as the typing takes. The lock keeps two dictations from
            # interleaving their keystrokes.
            with self._typing_lock:
                try:
                    # A small per-character delay matters here: some target
                    # apps (rich-text/JS-driven inputs, e.g. a chat box in an
                    # Electron/web-based app) can't keep up with instantly-
                    # injected keystrokes and scramble the character order.
                    # 12ms/char wasn't enough for some inputs; the 30ms default
                    # still reads as instant but gives slower inputs room, and
                    # Settings lets users raise it for the slowest editors.
                    keyboard.write(text, delay=typing_delay)
                    self._last_typed_text = text
                    self._last_typed_hwnd = target_hwnd
                    if send_after:
                        # A moment for the app to take the last characters.
                        time.sleep(0.15)
                        keyboard.send("enter")
                        # Sent, so "scratch that" must not Backspace into
                        # whatever comes next in that window.
                        self._last_typed_text = ""
                except Exception:  # noqa: BLE001
                    pass

        threading.Thread(target=_type, daemon=True).start()

    _EDITING_STATUS_TEXT = {
        "all": "Undid last dictation",
        "word": "Deleted last word",
        "sentence": "Deleted last sentence",
    }

    def _handle_editing_command(self, mode: str) -> None:
        """Spoken "scratch that" / "delete last word" / "delete last
        sentence" -- Backspace out some or all of the last text VoxScribe
        itself typed, but only if the focused window is still the same one
        it was typed into. If the user has since switched windows, refuse
        rather than guess: blindly Backspacing into the wrong window could
        delete text the user never dictated. Updates `_last_typed_text` to
        whatever's left rather than clearing it outright (except for "all"),
        so a second "delete last word" in a row keeps peeling words off."""
        self.record_button.setEnabled(True)
        self._set_import_enabled(True)
        if not self._last_typed_text:
            self._set_status("Nothing to undo", "ready")
            self._indicator.flash_error("Nothing to undo")
            return

        current_hwnd = foreground_window_handle()
        if self._last_typed_hwnd is None or current_hwnd != self._last_typed_hwnd:
            self._set_status("Can't undo -- active window changed", "error")
            self._indicator.flash_error("Can't undo, window changed")
            return

        # Refocus the window the text was typed into (already confirmed to be
        # the focused one above), never the window the command was spoken in:
        # those can differ, and Backspace must only ever hit the right one.
        focus_window(self._last_typed_hwnd)

        remaining_text, backspace_count = compute_deletion(self._last_typed_text, mode)

        try:
            for _ in range(backspace_count):
                keyboard.send("backspace")
        except Exception:  # noqa: BLE001
            pass

        self._last_typed_text = remaining_text
        if not remaining_text:
            self._last_typed_hwnd = None
        self._set_status(self._EDITING_STATUS_TEXT[mode], "ready")
        self._indicator.flash_success(self._EDITING_STATUS_TEXT[mode])

    def _after_typing(self, command) -> None:
        """Runs a spoken command once the dictation before it has been typed
        in full. Typing a long dictation takes seconds, and until it is done the
        last typed text is still the one before: "scratch that" would remove
        the wrong text and "send it" would send half a message."""
        if self._typing_lock.locked():
            QTimer.singleShot(100, lambda: self._after_typing(command))
            return
        command()

    def _handle_rewrite_command(self, rewrite, status_text: str) -> None:
        """Spoken "capitalize that", "all caps", "replace X with Y": retypes
        only the part of the last dictation that changes, in the window it was
        typed into. Like undo, it refuses if the active window has changed,
        rather than Backspace into text the user never dictated."""
        self.record_button.setEnabled(True)
        self._set_import_enabled(True)
        old = self._last_typed_text
        if not old:
            self._set_status("Nothing to change", "ready")
            self._indicator.flash_error("Nothing to change")
            return
        if self._last_typed_hwnd is None or foreground_window_handle() != self._last_typed_hwnd:
            self._set_status("Can't change -- active window changed", "error")
            self._indicator.flash_error("Can't change, window changed")
            return
        new = rewrite(old)
        if new is None:
            self._set_status("Nothing to change", "ready")
            self._indicator.flash_error("Nothing to change")
            return

        focus_window(self._last_typed_hwnd)
        backspaces, to_type = compute_rewrite(old, new)
        typing_delay = hotkey_settings.get_typing_delay_ms() / 1000
        self._last_typed_text = new

        def _retype() -> None:
            with self._typing_lock:
                try:
                    for _ in range(backspaces):
                        keyboard.send("backspace")
                    if to_type:
                        keyboard.write(to_type, delay=typing_delay)
                except Exception:  # noqa: BLE001
                    pass

        threading.Thread(target=_retype, daemon=True).start()
        self._set_status(status_text, "ready")
        self._indicator.flash_success(status_text)

    def _handle_send_command(self) -> None:
        """Spoken "send it" (opt-in): presses Enter in the app being dictated
        into. Refuses if that window is no longer the active one, and when
        VoxScribe itself is the active window, where Enter means nothing."""
        self.record_button.setEnabled(True)
        self._set_import_enabled(True)
        if self.isActiveWindow():
            self._set_status("Click into the app you want to send from first", "error")
            self._indicator.flash_error("Click into an app first")
            return
        if (
            self._last_typed_hwnd is not None
            and foreground_window_handle() != self._last_typed_hwnd
        ):
            self._set_status("Can't send -- active window changed", "error")
            self._indicator.flash_error("Can't send, window changed")
            return
        try:
            keyboard.send("enter")
        except Exception:  # noqa: BLE001
            pass
        # It was sent, so a later "scratch that" must not Backspace into
        # whatever comes next in that window.
        self._last_typed_text = ""
        self._last_typed_hwnd = None
        self._set_status("Pressed Enter", "ready")
        self._indicator.flash_success("Sent")

    def _on_transcribe_failed(self, message: str) -> None:
        self.transcript_area.append(f"[error] {message}")
        self._set_status("Ready", "ready")
        self.record_button.setEnabled(True)
        self._set_import_enabled(True)
        self._indicator.flash_error("Transcription failed")

    # -- import existing audio/video file ---------------------------------

    def import_audio_file(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Import Audio or Video",
            "",
            "Audio/Video Files (*.wav *.mp3 *.m4a *.mp4 *.mov *.flac *.ogg *.wma *.aac *.webm);;"
            "All Files (*)",
        )
        if paths:
            self._begin_import(paths)

    def import_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Choose a folder of audio or video files"
        )
        if folder:
            self._begin_import([folder])

    def dragEnterEvent(self, event) -> None:  # noqa: N802, ANN001
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802, ANN001
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            event.acceptProposedAction()
            self._begin_import(paths)

    def _begin_import(self, paths: list[str], retry: bool = False) -> None:
        """Starts an import from picked files, a picked folder or a drop. One
        file is free; several files or a folder is a batch: Pro, with a couple
        of free runs so it can be tried first."""
        if not self.import_button.isEnabled() or self._import_active():
            self._set_status("Wait for the current job to finish", "error")
            return
        files = batch.collect_media(paths)
        if not files:
            self._set_status("No audio or video files found", "error")
            return
        is_batch = len(files) > 1 or any(os.path.isdir(p) for p in paths)

        trial_note = ""
        if is_batch and not retry and not hotkey_license.is_pro():
            if hotkey_settings.get_batch_trials_left() <= 0:
                self._offer_batch_pro(files)
                return
            left = hotkey_settings.use_batch_trial()
            trial_note = (
                f"Free batch run used, {left} left. Batch import is a Pro feature."
                if left
                else "Last free batch run used. Batch import is a Pro feature."
            )

        if is_batch and not self.export_srt_checkbox.isChecked():
            # A batch that saves no files would only fill the transcript box.
            self.export_srt_checkbox.setChecked(True)
            trial_note = (trial_note + " " if trial_note else "") + (
                "Save .srt captions was turned on so the batch saves a file for each one."
            )

        skipped: list[str] = []
        if is_batch and self.export_srt_checkbox.isChecked():
            files, skipped = batch.split_done(files)
            if not files:
                self._set_status("Every file there already has an .srt", "ready")
                return

        if trial_note:
            self.transcript_area.append(trial_note)
        self._import_queue = list(files)
        self._batch = (
            {
                "total": len(files),
                "done": 0,
                "failed": 0,
                "skipped": len(skipped),
                "saved": 0,
                "paths": list(files),
                "results": [{"path": p, "status": "skipped"} for p in skipped],
                "cancelled": False,
                "paused": False,
            }
            if is_batch
            else None
        )
        self._batch_folder = None
        self._batch_retry_button.hide()
        self._retry_paths = []
        if is_batch:
            animate_progress(self._batch_progress, 0)
            self._batch_progress.show()
            self._batch_pause_button.setText("Pause")
            self._batch_pause_button.show()
            self._batch_cancel_button.show()
            self._batch_open_button.hide()
            self._batch_label.setText(f"Starting {len(files)} files...")
            self._batch_bar.show()
        else:
            self._batch_bar.hide()
        self.record_button.setEnabled(False)
        self._set_import_enabled(False)
        self._process_next_import_file()

    def _offer_batch_pro(self, files: list[str]) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("Batch import is a Pro feature")
        box.setText(
            f"That is {len(files)} files. Importing several files or a folder at once "
            "is part of VoxScribe Pro, and your 2 free batch runs are used up."
        )
        box.setInformativeText(
            "You can still import one file at a time for free, or get Pro once for $14."
        )
        pro_button = box.addButton("Get Pro", QMessageBox.AcceptRole)
        first_button = box.addButton("Import first file only", QMessageBox.ActionRole)
        box.addButton("Cancel", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is pro_button:
            webbrowser.open("https://hmamster3.gumroad.com/l/tbsfom")
        elif box.clickedButton() is first_button:
            self._begin_import(files[:1])

    def _toggle_import_pause(self) -> None:
        if self._batch is None or self._file_worker is None:
            return
        paused = not self._batch["paused"]
        self._batch["paused"] = paused
        self._file_worker.set_paused(paused)
        self._batch_pause_button.setText("Resume" if paused else "Pause")
        self._refresh_batch_label(None)

    def _cancel_import(self) -> None:
        if self._batch is None:
            return
        self._batch["cancelled"] = True
        self._import_queue = []
        self._batch_label.setText("Stopping after this part...")
        if self._file_worker is not None:
            self._file_worker.request_stop()

    def _retry_batch(self) -> None:
        paths = list(self._retry_paths)
        if paths:
            self._begin_import(paths, retry=True)

    def _open_batch_folder(self) -> None:
        if self._batch_folder and os.path.isdir(self._batch_folder):
            os.startfile(self._batch_folder)  # noqa: S606

    def _refresh_batch_label(self, percent: int | None) -> None:
        if self._batch is None:
            return
        b = self._batch
        number = min(b["total"], b["done"] + b["failed"] + 1)
        text = f"File {number} of {b['total']}"
        if b["paused"]:
            text += " (paused)"
        elif percent is not None:
            text += f", {percent}%"
        self._batch_label.setText(text)

    def _on_import_progress(self, percent: int) -> None:
        if self._batch is None:
            return
        b = self._batch
        animate_progress(
            self._batch_progress,
            batch.overall_percent(b["done"] + b["failed"], b["total"], percent),
        )
        self._refresh_batch_label(percent)

    def _on_import_cancelled(self) -> None:
        self._finish_import()

    def _finish_import(self) -> None:
        self.record_button.setEnabled(True)
        self._set_import_enabled(True)
        self._set_status("Ready", "ready")
        self._indicator.hide_indicator()
        b = self._batch
        self._batch = None
        if b is None:
            return
        summary = batch.format_summary(
            b["total"], b["done"], b["failed"], b["skipped"], b["saved"], b["cancelled"]
        )
        self.transcript_area.append(summary)
        handled = {r["path"] for r in b["results"]}
        results = b["results"] + [
            {"path": p, "status": "not run"} for p in b["paths"] if p not in handled
        ]
        folder = batch.common_folder(b["paths"])
        for line in batch.format_report(results, folder):
            self.transcript_area.append(line)
        self._retry_paths = batch.to_retry(results)
        self._batch_retry_button.setText(
            f"Retry {len(self._retry_paths)} file{'s' if len(self._retry_paths) != 1 else ''}"
        )
        self._batch_retry_button.setVisible(bool(self._retry_paths))
        self._batch_label.setText(summary)
        if not b["cancelled"]:
            animate_progress(self._batch_progress, 100)
        self._batch_pause_button.hide()
        self._batch_cancel_button.hide()
        self._batch_progress.hide()
        self._batch_folder = batch.common_folder(b["paths"])
        self._batch_open_button.setVisible(bool(self._batch_folder))
        if self.tray_icon is not None:
            self._tray_notify("VoxScribe", summary, QSystemTrayIcon.MessageIcon.Information, 5000)

    def _process_next_import_file(self) -> None:
        if not self._import_queue:
            self._finish_import()
            return

        path = self._import_queue.pop(0)
        remaining = len(self._import_queue)
        if self._batch is not None:
            status = f"Transcribing {Path(path).name}..."
            self._refresh_batch_label(0)
        else:
            status = (
                f"Transcribing file... ({remaining} more queued)"
                if remaining
                else "Transcribing file..."
            )
        self._set_status(status, "transcribing")
        self._indicator.show_status("transcribing")

        # Keep the previous worker referenced until its thread has really
        # finished: this slot runs right after its last emit(), so the QThread
        # may still be exiting, and dropping the last reference would destroy
        # a running thread.
        self._retired_file_workers = [w for w in self._retired_file_workers if w.isRunning()]
        if self._file_worker is not None and self._file_worker.isRunning():
            self._retired_file_workers.append(self._file_worker)

        self._file_worker = FileTranscribeThread(
            self.transcriber,
            path,
            hotkey_settings.get_language(),
            hotkey_settings.custom_vocabulary_prompt(),
            "translate" if hotkey_settings.get_translate_to_english_enabled() else "transcribe",
            self.export_srt_checkbox.isChecked(),
            self.export_extras_checkbox.isChecked() and hotkey_license.is_pro(),
            self.label_speakers_checkbox.isChecked() and hotkey_license.is_pro(),
            hotkey_settings.get_speaker_count(),
            hotkey_settings.get_speaker_names(),
            hotkey_settings.get_caption_line_chars(),
        )
        if self._batch is not None and self._batch["paused"]:
            self._file_worker.set_paused(True)
        self._file_worker.status.connect(lambda message: self._set_status(message, "transcribing"))
        self._file_worker.progress.connect(self._on_import_progress)
        self._file_worker.cancelled.connect(self._on_import_cancelled)
        self._file_worker.done.connect(lambda text, p=path: self._on_file_transcribed(text, p))
        self._file_worker.failed.connect(
            lambda message, p=path: self._on_file_transcribe_failed(message, p)
        )
        self._file_worker.start()

    def _on_file_transcribed(self, text: str, path: str) -> None:
        if text and hotkey_settings.get_cleanup_enabled():
            text = clean_transcript(text)
        if text:
            text = replacements.apply_replacements(text)
        label = f"[{Path(path).name}]"
        self.transcript_area.append(f"{label} {text if text else '[no speech recognized]'}")
        if self._batch is not None:
            self._batch["done"] += 1
            if self._file_worker is not None and self._file_worker.srt_path:
                self._batch["saved"] += 1
            self._batch["results"].append(
                {
                    "path": path,
                    "status": "done",
                    "srt": self._file_worker.srt_path if self._file_worker else None,
                }
            )
        if self._file_worker is not None and self._file_worker.srt_path:
            self.transcript_area.append(f"  saved: {Path(self._file_worker.srt_path).name}")
        if self._file_worker is not None and self._file_worker.review_total:
            worker = self._file_worker
            self.transcript_area.append(
                f"  review: {worker.review_total} caption card"
                f"{'s' if worker.review_total != 1 else ''} to check "
                "(flagged only, nothing was changed)"
            )
            for note in worker.review_notes:
                self.transcript_area.append(f"    {note}")
        if self._file_worker is not None and self._file_worker.speaker_error:
            self.transcript_area.append(
                f"  could not label speakers: {self._file_worker.speaker_error}"
            )
        if self._file_worker is not None and self._file_worker.extra_paths:
            names = ", ".join(Path(p).name for p in self._file_worker.extra_paths)
            self.transcript_area.append(f"  saved: {names}")
        self._process_next_import_file()

    def _on_file_transcribe_failed(self, message: str, path: str) -> None:
        self.transcript_area.append(f"[{Path(path).name}] [error] {message}")
        if self._batch is not None:
            self._batch["failed"] += 1
            self._batch["results"].append({"path": path, "status": "failed", "error": message})
        self._process_next_import_file()
