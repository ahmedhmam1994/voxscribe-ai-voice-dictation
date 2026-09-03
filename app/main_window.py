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
import webbrowser
import winsound
from datetime import datetime
from pathlib import Path

import keyboard
import numpy as np
import sounddevice as sd
from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    QPropertyAnimation,
    QRectF,
    QSequentialAnimationGroup,
    QSize,
    Qt,
    QThread,
    QTimer,
    Signal,
)
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.floating_indicator import FloatingIndicator
from app.version import __version__
from core import history, snippets
from core import license as hotkey_license
from core import settings as hotkey_settings
from core.audio_capture import (
    SAMPLE_RATE,
    device_native_samplerate,
    list_input_devices,
    peak_levels,
    resample_to_16k,
    resolve_input_device,
)
from core.cleanup import clean_transcript
from core.crash_reporter import LOG_DIR as CRASH_LOG_DIR
from core.focused_window import foreground_process_name
from core.transcribe import Transcriber
from core.updater import UpdateCheckThread, UpdateDownloadThread, UpdateInfo

ICON_PATH = Path(__file__).parent / "icon.ico"
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


# -- hand-drawn vector icons ------------------------------------------------
# No icon library is wired into this desktop app, and QSS/Qt widgets have no
# equivalent of a web icon font. Rather than fall back to unicode glyphs
# (which render inconsistently across Windows font fallback), icons are
# drawn directly with QPainter at a fixed stroke weight -- a real, if tiny,
# authored icon set instead of text-only buttons.
_ICON_STROKE = 1.6


def _new_icon_painter(size: int, color: str) -> tuple[QPixmap, QPainter]:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(_ICON_STROKE)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    return pixmap, painter


def _icon_mic(size: int = 22, color: str = "#ffffff") -> QIcon:
    pixmap, painter = _new_icon_painter(size, color)
    s = size
    body = QRectF(s * 0.37, s * 0.08, s * 0.26, s * 0.42)
    painter.drawRoundedRect(body, body.width() / 2, body.width() / 2)
    bracket = QRectF(s * 0.20, s * 0.28, s * 0.60, s * 0.50)
    painter.drawArc(bracket, 200 * 16, 140 * 16)
    painter.drawLine(int(s * 0.5), int(s * 0.72), int(s * 0.5), int(s * 0.88))
    painter.drawLine(int(s * 0.34), int(s * 0.88), int(s * 0.66), int(s * 0.88))
    painter.end()
    return QIcon(pixmap)


def _icon_stop(size: int = 22, color: str = "#ffffff") -> QIcon:
    pixmap, painter = _new_icon_painter(size, color)
    s = size
    painter.setBrush(QColor(color))
    rect = QRectF(s * 0.30, s * 0.30, s * 0.40, s * 0.40)
    painter.drawRoundedRect(rect, s * 0.06, s * 0.06)
    painter.end()
    return QIcon(pixmap)


def _icon_save(size: int = 16, color: str = TEXT_PRIMARY) -> QIcon:
    pixmap, painter = _new_icon_painter(size, color)
    s = size
    painter.drawLine(int(s * 0.5), int(s * 0.14), int(s * 0.5), int(s * 0.62))
    path = QPainterPath()
    path.moveTo(s * 0.32, s * 0.44)
    path.lineTo(s * 0.5, s * 0.64)
    path.lineTo(s * 0.68, s * 0.44)
    painter.drawPath(path)
    painter.drawLine(int(s * 0.18), int(s * 0.82), int(s * 0.82), int(s * 0.82))
    painter.end()
    return QIcon(pixmap)


def _icon_copy(size: int = 16, color: str = TEXT_PRIMARY) -> QIcon:
    pixmap, painter = _new_icon_painter(size, color)
    s = size
    back = QRectF(s * 0.16, s * 0.16, s * 0.52, s * 0.52)
    painter.drawRoundedRect(back, s * 0.08, s * 0.08)
    front = QRectF(s * 0.34, s * 0.34, s * 0.52, s * 0.52)
    painter.setPen(QPen(QColor(color), _ICON_STROKE))
    painter.setBrush(QColor(BG_CARD))
    painter.drawRoundedRect(front, s * 0.08, s * 0.08)
    painter.end()
    return QIcon(pixmap)


def _icon_clear(size: int = 16, color: str = TEXT_PRIMARY) -> QIcon:
    pixmap, painter = _new_icon_painter(size, color)
    s = size
    painter.drawLine(int(s * 0.22), int(s * 0.30), int(s * 0.78), int(s * 0.30))
    painter.drawLine(int(s * 0.40), int(s * 0.18), int(s * 0.60), int(s * 0.18))
    body = QRectF(s * 0.28, s * 0.30, s * 0.44, s * 0.56)
    painter.drawRoundedRect(body, s * 0.05, s * 0.05)
    painter.drawLine(int(s * 0.42), int(s * 0.40), int(s * 0.42), int(s * 0.74))
    painter.drawLine(int(s * 0.58), int(s * 0.40), int(s * 0.58), int(s * 0.74))
    painter.end()
    return QIcon(pixmap)


def _icon_settings(size: int = 18, color: str = TEXT_MUTED) -> QIcon:
    pixmap, painter = _new_icon_painter(size, color)
    s = size
    rows_and_knobs = ((0.30, 0.62), (0.52, 0.36), (0.74, 0.56))
    for y, _knob_x in rows_and_knobs:
        painter.drawLine(int(s * 0.10), int(s * y), int(s * 0.90), int(s * y))
    painter.setBrush(QColor(color))
    for y, knob_x in rows_and_knobs:
        painter.drawEllipse(QRectF(s * knob_x - s * 0.08, s * y - s * 0.08, s * 0.16, s * 0.16))
    painter.end()
    return QIcon(pixmap)


def _icon_globe(size: int = 13, color: str = TEXT_MUTED) -> QIcon:
    pixmap, painter = _new_icon_painter(size, color)
    s = size
    painter.drawEllipse(QRectF(s * 0.08, s * 0.08, s * 0.84, s * 0.84))
    painter.drawLine(int(s * 0.08), int(s * 0.5), int(s * 0.92), int(s * 0.5))
    painter.drawEllipse(QRectF(s * 0.32, s * 0.08, s * 0.36, s * 0.84))
    painter.end()
    return QIcon(pixmap)


def _icon_keyboard(size: int = 14, color: str = TEXT_FAINT) -> QIcon:
    pixmap, painter = _new_icon_painter(size, color)
    s = size
    body = QRectF(s * 0.08, s * 0.24, s * 0.84, s * 0.52)
    painter.drawRoundedRect(body, s * 0.08, s * 0.08)
    for cx in (0.24, 0.40, 0.56, 0.72):
        painter.drawPoint(int(s * cx), int(s * 0.42))
    painter.drawLine(int(s * 0.24), int(s * 0.60), int(s * 0.76), int(s * 0.60))
    painter.end()
    return QIcon(pixmap)


def _icon_insights(size: int = 18, color: str = TEXT_MUTED) -> QIcon:
    pixmap, painter = _new_icon_painter(size, color)
    s = size
    bars = ((0.20, 0.45), (0.46, 0.25), (0.72, 0.60))
    for x, h in bars:
        rect = QRectF(s * x, s * (0.86 - h), s * 0.18, s * h)
        painter.drawRoundedRect(rect, s * 0.03, s * 0.03)
    painter.drawLine(int(s * 0.10), int(s * 0.86), int(s * 0.90), int(s * 0.86))
    painter.end()
    return QIcon(pixmap)


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
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #9686f8, stop:1 #7566e0);
    color: #ffffff;
    font-size: 15px;
    font-weight: 700;
    border: none;
    border-radius: 12px;
    padding: 10px 16px;
}}
QPushButton#recordButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #a89cf9, stop:1 #8574ea);
}}
QPushButton#recordButton:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #8574ea, stop:1 #6a5cd0);
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
    background: rgba(139, 124, 246, 0.14);
}}
QPushButton#primaryOutlineButton:pressed {{
    background: rgba(139, 124, 246, 0.24);
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
        stop:0 #6f5ff0, stop:0.5 {ACCENT}, stop:1 #c48cf2);
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
    background: rgba(139, 124, 246, 0.16);
    color: {TEXT_PRIMARY};
}}

QWidget#heroBanner {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #372f66, stop:0.55 #5d4bb0, stop:1 #7c5cc9);
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
QDialog {{
    background: {BG_WINDOW};
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


def _play_tone(frequency: int, duration_ms: int) -> None:
    """Fires winsound.Beep() on a short-lived background thread so a start/
    stop sound cue (Settings -> Play a sound) can't block the Qt event loop
    for its duration -- Beep() is a blocking call. Best-effort: some
    systems/sandboxes have no audio device, so failures are swallowed
    rather than surfaced as an error over a cosmetic feature."""
    def _beep() -> None:
        try:
            winsound.Beep(frequency, duration_ms)
        except OSError:
            pass

    threading.Thread(target=_beep, daemon=True).start()


def _play_start_sound() -> None:
    if hotkey_settings.get_sound_enabled():
        _play_tone(880, 90)


def _play_stop_sound() -> None:
    if hotkey_settings.get_sound_enabled():
        _play_tone(440, 90)


class ModelLoaderThread(QThread):
    done = Signal(object)
    failed = Signal(str)

    def run(self) -> None:
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
            transcriber = Transcriber(model_size=model_size)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
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
    ) -> None:
        super().__init__()
        self.transcriber = transcriber
        self.audio = audio
        self.language = language
        self.initial_prompt = initial_prompt

    def run(self) -> None:
        try:
            text = self.transcriber.transcribe(
                self.audio, language=self.language, initial_prompt=self.initial_prompt
            )
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.done.emit(text)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("VoxScribe")
        self.resize(960, 620)
        self.setMinimumSize(760, 520)
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
        self._loader: ModelLoaderThread | None = None
        self._worker: TranscribeThread | None = None

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
        settings_nav_button.clicked.connect(self._open_settings_dialog)
        sidebar_layout.addWidget(settings_nav_button)

        body_row.addWidget(sidebar)
        body_row.addWidget(self._pages, stretch=1)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(14)
        self._pages.addWidget(content)

        hero = QWidget()
        hero.setObjectName("heroBanner")
        hero.setFixedHeight(84)
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(20, 14, 20, 14)
        hero_layout.setSpacing(2)
        hero_title = QLabel("Hold to talk, anywhere")
        hero_title.setObjectName("heroTitle")
        hero_layout.addWidget(hero_title)
        hero_subtitle = QLabel(
            "Speak, release, and it's typed straight into whatever you're focused on."
        )
        hero_subtitle.setObjectName("heroSubtitle")
        hero_layout.addWidget(hero_subtitle)
        hero_layout.addStretch(1)
        layout.addWidget(hero)

        status_row = QHBoxLayout()
        self.status_pill = StatusPill()
        status_row.addWidget(self.status_pill)
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
        self.record_button.setMinimumHeight(52)
        self.record_button.setCursor(Qt.PointingHandCursor)
        self.record_button.setIcon(self._mic_icon)
        self.record_button.setIconSize(QSize(20, 20))
        self.record_button.clicked.connect(self.toggle_recording)
        layout.addWidget(self.record_button)

        # Soft glow beneath the record button -- violet at rest, shifting to
        # green and pulsing while actively recording -- so the primary
        # action reads as elevated/"live" rather than a flat rectangle.
        self._record_shadow = QGraphicsDropShadowEffect(self.record_button)
        self._record_shadow.setOffset(0, 6)
        self._record_shadow.setBlurRadius(24)
        self._record_shadow.setColor(QColor(139, 124, 246, 110))
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

        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        self.save_button = QPushButton("Save Transcript")
        self.save_button.setObjectName("primaryOutlineButton")
        self.save_button.setEnabled(False)
        self.save_button.setMinimumHeight(38)
        self.save_button.setCursor(Qt.PointingHandCursor)
        self.save_button.setIcon(_icon_save(16, ACCENT))
        self.save_button.setIconSize(QSize(15, 15))
        self.save_button.clicked.connect(self.save_transcript)
        button_row.addWidget(self.save_button)

        self.copy_button = QPushButton("Copy")
        self.copy_button.setObjectName("secondaryButton")
        self.copy_button.setEnabled(False)
        self.copy_button.setMinimumHeight(38)
        self.copy_button.setCursor(Qt.PointingHandCursor)
        self.copy_button.setIcon(_icon_copy(16, TEXT_PRIMARY))
        self.copy_button.setIconSize(QSize(15, 15))
        self.copy_button.clicked.connect(self.copy_transcript)
        button_row.addWidget(self.copy_button)

        self.clear_button = QPushButton("Clear")
        self.clear_button.setObjectName("ghostButton")
        self.clear_button.setEnabled(False)
        self.clear_button.setMinimumHeight(38)
        self.clear_button.setCursor(Qt.PointingHandCursor)
        self.clear_button.setIcon(_icon_clear(16, TEXT_MUTED))
        self.clear_button.setIconSize(QSize(15, 15))
        self.clear_button.clicked.connect(self.clear_transcript)
        button_row.addWidget(self.clear_button)

        layout.addLayout(button_row)

        transcript_label = QLabel("TRANSCRIPT")
        transcript_label.setObjectName("transcriptCaption")
        layout.addWidget(transcript_label)

        self.transcript_area = QTextEdit()
        self.transcript_area.setObjectName("transcriptArea")
        self.transcript_area.setProperty("hasContent", False)
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
        self._hotkey_press_hook = None
        self._hotkey_release_hook = None
        self._hotkey_registration_error: str | None = None

        # Hotkey hint row: icon + "Hold [KEY] anywhere..." with the key
        # itself rendered as a small badge, so the hold-to-talk hotkey (the
        # app's primary interaction) is more visible than plain muted text.
        hint_row = QHBoxLayout()
        hint_row.setSpacing(6)
        hint_row.setContentsMargins(2, 2, 2, 0)

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

        history_label = QLabel("TODAY")
        history_label.setObjectName("transcriptCaption")
        layout.addWidget(history_label)

        history_scroll = QScrollArea()
        history_scroll.setObjectName("historyScroll")
        history_scroll.setWidgetResizable(True)
        history_scroll.setFrameShape(QScrollArea.NoFrame)
        history_scroll.setFixedHeight(120)
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

        self._setup_tray_icon()

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

    def _register_global_hotkey(self) -> None:
        """(Re)registers the global hold-to-talk hotkey as self._hotkey.
        Safe to call again after changing the hotkey (see
        _open_settings_dialog) -- unhooks the previous registration first."""
        for hook in (self._hotkey_press_hook, self._hotkey_release_hook):
            if hook is not None:
                try:
                    keyboard.unhook(hook)
                except (KeyError, ValueError):
                    pass
        self._hotkey_press_hook = None
        self._hotkey_release_hook = None
        self._hotkey_registration_error = None

        try:
            self._hotkey_press_hook = keyboard.on_press_key(
                self._hotkey, lambda e: self._hotkey_bridge.press_requested.emit()
            )
            self._hotkey_release_hook = keyboard.on_release_key(
                self._hotkey, lambda e: self._hotkey_bridge.release_requested.emit()
            )
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
                "anywhere to talk — release to stop. Text is typed directly "
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
        combo = QComboBox()
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(20)
        combo.setMinimumHeight(36)
        return combo

    def _open_settings_dialog(self) -> None:
        """The app's Settings window, scrollable since it now covers a real
        set of options: hotkey + talk mode, microphone, dictation language
        + Whisper model size, custom vocabulary, filler-word cleanup and
        recording-sound toggles, a disabled-apps list, usage statistics,
        and "start with Windows". Reachable from the in-window gear button
        and the tray menu's "Settings..." entry -- previously only a bare
        hotkey combo box existed, with no other options exposed anywhere
        in the app."""
        dialog = QDialog(self)
        dialog.setWindowTitle("VoxScribe Settings")
        dialog.setStyleSheet(SETTINGS_DIALOG_STYLESHEET)
        # Fixed, not just minimum, width: with this many sections now (some
        # with long hint text), Qt's own layout sizing otherwise overrides a
        # plain resize() and widens the dialog to fit the longest unwrapped
        # label, which triggers an unwanted horizontal scrollbar inside the
        # QScrollArea below -- confirmed via an actual screenshot, not
        # assumed.
        dialog.setFixedWidth(420)
        dialog.resize(420, 600)

        outer_layout = QVBoxLayout(dialog)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        outer_layout.addWidget(scroll, stretch=1)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 12)
        layout.setSpacing(16)
        scroll.setWidget(content)

        license_section_label = QLabel("VOXSCRIBE PRO")
        license_section_label.setObjectName("settingsSectionLabel")
        layout.addWidget(license_section_label)

        license_status_label = QLabel()
        license_status_label.setWordWrap(True)
        license_status_label.setObjectName("settingsHint")
        layout.addWidget(license_status_label)

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
                license_key_edit.hide()
                license_unlock_button.hide()
                license_remove_button.show()
            else:
                license_status_label.setText(
                    "Free tier. Paste a Pro license key below to unlock Snippets."
                )
                license_key_edit.show()
                license_unlock_button.show()
                license_remove_button.hide()

        def _try_unlock_license() -> None:
            if hotkey_license.set_license_key(license_key_edit.text()):
                license_key_edit.clear()
                _refresh_license_ui()
            else:
                license_status_label.setText(
                    "That key isn't valid -- check for typos and try again."
                )

        def _remove_license() -> None:
            hotkey_license.clear_license_key()
            _refresh_license_ui()

        license_unlock_button.clicked.connect(_try_unlock_license)
        license_remove_button.clicked.connect(_remove_license)
        _refresh_license_ui()

        hotkey_label = QLabel("HOLD-TO-TALK HOTKEY")
        hotkey_label.setObjectName("settingsSectionLabel")
        layout.addWidget(hotkey_label)

        combo = self._new_settings_combo()
        for key in hotkey_settings.AVAILABLE_HOTKEYS:
            combo.addItem(key.upper(), key)
        combo.setCurrentIndex(hotkey_settings.AVAILABLE_HOTKEYS.index(self._hotkey))
        layout.addWidget(combo)

        talk_mode_combo = self._new_settings_combo()
        for mode, label in hotkey_settings.AVAILABLE_TALK_MODES:
            talk_mode_combo.addItem(label, mode)
        current_talk_mode = hotkey_settings.get_talk_mode()
        for i in range(talk_mode_combo.count()):
            if talk_mode_combo.itemData(i) == current_talk_mode:
                talk_mode_combo.setCurrentIndex(i)
                break
        layout.addWidget(talk_mode_combo)

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
        dialog.finished.connect(lambda _result: _stop_mic_test())

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

        model_label = QLabel("WHISPER MODEL SIZE")
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

        def _update_model_lock_state() -> None:
            unlocked = hotkey_license.is_pro()
            item_model = model_combo.model()
            for i in range(model_combo.count()):
                if model_combo.itemData(i) in hotkey_settings.PRO_MODEL_SIZES:
                    item_model.item(i).setEnabled(unlocked)
            model_hint.setText(
                "Takes effect after restarting VoxScribe. Switching to a size not "
                "already downloaded needs internet on next launch."
                + ("" if unlocked else " Medium/Large require Pro.")
            )

        _update_model_lock_state()
        license_unlock_button.clicked.connect(_update_model_lock_state)
        license_remove_button.clicked.connect(_update_model_lock_state)

        vocab_label = QLabel("CUSTOM VOCABULARY")
        vocab_label.setObjectName("settingsSectionLabel")
        layout.addWidget(vocab_label)

        vocab_edit = QLineEdit()
        vocab_edit.setPlaceholderText("e.g. VoxScribe, Ahmed, faster-whisper")
        vocab_edit.setText(", ".join(hotkey_settings.get_custom_vocabulary()))
        vocab_edit.setMinimumHeight(36)
        layout.addWidget(vocab_edit)

        vocab_hint = QLabel(
            "Names, acronyms, or terms Whisper tends to mishear — comma-separated. "
            "Nudges recognition toward them; doesn't guarantee a match."
        )
        vocab_hint.setObjectName("settingsHint")
        vocab_hint.setWordWrap(True)
        layout.addWidget(vocab_hint)

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

        cleanup_checkbox = QCheckBox("Clean up filler words (\"um\", \"uh\", \"like\")")
        cleanup_checkbox.setChecked(hotkey_settings.get_cleanup_enabled())
        layout.addWidget(cleanup_checkbox)

        sound_checkbox = QCheckBox("Play a sound when recording starts/stops")
        sound_checkbox.setChecked(hotkey_settings.get_sound_enabled())
        layout.addWidget(sound_checkbox)

        excluded_label = QLabel("DISABLED APPS")
        excluded_label.setObjectName("settingsSectionLabel")
        layout.addWidget(excluded_label)

        excluded_edit = QLineEdit()
        excluded_edit.setPlaceholderText("e.g. keepass.exe, bitwarden.exe")
        excluded_edit.setText(", ".join(hotkey_settings.get_excluded_apps()))
        excluded_edit.setMinimumHeight(36)
        layout.addWidget(excluded_edit)

        excluded_hint = QLabel(
            "VoxScribe won't record while one of these apps is focused — comma-"
            "separated executable names, e.g. a password manager."
        )
        excluded_hint.setObjectName("settingsHint")
        excluded_hint.setWordWrap(True)
        layout.addWidget(excluded_hint)

        stats_label = QLabel("STATISTICS")
        stats_label.setObjectName("settingsSectionLabel")
        layout.addWidget(stats_label)

        sessions, words = hotkey_settings.get_stats()
        stats_value = QLabel(
            f"{sessions:,} dictation{'s' if sessions != 1 else ''} · {words:,} words"
        )
        stats_value.setObjectName("settingsHint")
        layout.addWidget(stats_value)

        startup_label = QLabel("STARTUP")
        startup_label.setObjectName("settingsSectionLabel")
        layout.addWidget(startup_label)

        auto_start_checkbox = QCheckBox("Start VoxScribe automatically when Windows starts")
        auto_start_checkbox.setChecked(hotkey_settings.get_auto_start())
        layout.addWidget(auto_start_checkbox)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        button_row = QHBoxLayout()
        button_row.setContentsMargins(24, 8, 24, 16)
        button_row.addWidget(buttons)
        outer_layout.addLayout(button_row)

        if dialog.exec() != QDialog.Accepted:
            return

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

        new_language = language_combo.currentData()
        if new_language != current_language:
            hotkey_settings.set_language(new_language)
            self._refresh_language_badge()
            changes.append(f"Dictation language set to {language_combo.currentText()}.")

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

        new_cleanup_enabled = cleanup_checkbox.isChecked()
        if new_cleanup_enabled != hotkey_settings.get_cleanup_enabled():
            hotkey_settings.set_cleanup_enabled(new_cleanup_enabled)
            changes.append(
                "Filler-word cleanup enabled."
                if new_cleanup_enabled
                else "Filler-word cleanup disabled."
            )

        new_sound_enabled = sound_checkbox.isChecked()
        if new_sound_enabled != hotkey_settings.get_sound_enabled():
            hotkey_settings.set_sound_enabled(new_sound_enabled)
            changes.append(
                "Recording sounds enabled." if new_sound_enabled else "Recording sounds disabled."
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
            self.tray_icon.showMessage(
                "VoxScribe",
                " ".join(changes),
                QSystemTrayIcon.MessageIcon.Information,
                4000,
            )

    # -- system tray ------------------------------------------------------

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
                f"Couldn't register the {self._hotkey.upper()} hotkey (often needs "
                "admin rights). Open VoxScribe and use the Start/Stop button instead.",
                QSystemTrayIcon.MessageIcon.Warning,
                6000,
            )
        else:
            self.tray_icon.showMessage(
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

    def _on_update_found(self, info: UpdateInfo) -> None:
        self._pending_update_info = info
        self._downloaded_installer_path = None
        if self.tray_icon is None:
            return
        if info.asset_url:
            self.tray_icon.showMessage(
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
        # Three possible states, checked in order: a downloaded installer
        # ready to run, a download in progress (ignore the click), or an
        # update just found (start the download, or fall back to the
        # browser if the release has no .exe asset).
        if self._downloaded_installer_path:
            os.startfile(self._downloaded_installer_path)  # noqa: S606 -- Windows-only app
            self._downloaded_installer_path = None
            self._pending_update_info = None
            return

        if self._update_downloader is not None and self._update_downloader.isRunning():
            return

        info = self._pending_update_info
        if info is None:
            return

        if not info.asset_url or not info.asset_name:
            webbrowser.open(info.url)
            self._pending_update_info = None
            return

        if self.tray_icon is not None:
            self.tray_icon.showMessage(
                "VoxScribe",
                "Downloading the update...",
                QSystemTrayIcon.MessageIcon.Information,
                4000,
            )
        self._update_downloader = UpdateDownloadThread(info.asset_url, info.asset_name)
        self._update_downloader.done.connect(self._on_update_downloaded)
        self._update_downloader.failed.connect(self._on_update_download_failed)
        self._update_downloader.start()

    def _on_update_downloaded(self, path: str) -> None:
        self._downloaded_installer_path = path
        if self.tray_icon is not None:
            self.tray_icon.showMessage(
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
        if self.tray_icon is not None:
            self.tray_icon.showMessage(
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
            self._record_shadow.setColor(QColor(139, 124, 246, 110))
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
            self._indicator.show_status("not_ready")
            QTimer.singleShot(1500, self._indicator.hide_indicator)
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

    def _start_recording(self) -> None:
        excluded_process = foreground_process_name()
        if excluded_process and excluded_process in hotkey_settings.get_excluded_apps():
            self._hotkey_active_session = False
            self._set_status(f"Dictation disabled for {excluded_process}", "error")
            return

        self._chunks = []
        # Falls back to auto-detection if the user's chosen device (Settings
        # -> Microphone) has been unplugged/disconnected since it was picked.
        device = resolve_input_device(hotkey_settings.get_input_device())
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
        _play_start_sound()

    def _stop_recording(self) -> None:
        self.stream.stop()
        self.stream.close()
        self.stream = None
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

        self._worker = TranscribeThread(
            self.transcriber,
            audio,
            hotkey_settings.get_language(),
            hotkey_settings.custom_vocabulary_prompt(),
        )
        self._worker.done.connect(self._on_transcribed)
        self._worker.failed.connect(self._on_transcribe_failed)
        self._worker.start()

    def _on_transcribed(self, text: str) -> None:
        if text and hotkey_settings.get_cleanup_enabled():
            text = clean_transcript(text)
        if text and hotkey_license.is_pro():
            text = snippets.expand_snippet(text)
        self.transcript_area.append(text if text else "[no speech recognized]")
        self.record_button.setEnabled(True)
        self._indicator.hide_indicator()

        if text:
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

    def _switch_page(self, index: int) -> None:
        self._pages.setCurrentIndex(index)
        for i, btn in self._nav_buttons.items():
            btn.setChecked(i == index)
        if index == 1:
            self._refresh_insights()

    def _new_stat_card(self, label_text: str) -> tuple[QLabel, QWidget]:
        card = QWidget()
        card.setObjectName("statCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(4)

        value_label = QLabel("0")
        value_label.setObjectName("statCardValue")
        card_layout.addWidget(value_label)

        caption_label = QLabel(label_text)
        caption_label.setObjectName("statCardLabel")
        card_layout.addWidget(caption_label)

        return value_label, card

    def _build_insights_page(self) -> None:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(24, 20, 24, 18)
        page_layout.setSpacing(16)

        title = QLabel("Insights")
        title.setObjectName("pageTitle")
        page_layout.addWidget(title)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)
        self._stat_words_value, words_card = self._new_stat_card("Total words")
        self._stat_wpm_value, wpm_card = self._new_stat_card("Avg. words/min")
        self._stat_streak_value, streak_card = self._new_stat_card("Day streak")
        for card in (words_card, wpm_card, streak_card):
            cards_row.addWidget(card)
        page_layout.addLayout(cards_row)
        page_layout.addStretch(1)

        self._pages.addWidget(page)

    def _refresh_insights(self) -> None:
        stats = history.compute_stats()
        self._stat_words_value.setText(f"{stats['total_words']:,}")
        self._stat_wpm_value.setText(str(stats["wpm"]))
        self._stat_streak_value.setText(str(stats["streak_days"]))

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

        self._refresh_insights()

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
