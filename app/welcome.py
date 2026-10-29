"""First-run welcome: a short looping animation of the whole idea (hold the
hotkey, talk, let go, the words appear in the app you were typing in), so
someone who just installed VoxScribe understands it without reading.

VoxScribe starts hidden in the tray, so without this a brand-new install
shows nothing at all apart from a tray notification that is easy to miss.
Shown once, on the very first launch, and again from the tray menu's
"How to use VoxScribe".
"""

from __future__ import annotations

import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app import theme
from app.motion import animations_enabled

ACCENT = theme.qc("#3ecf8e")
AMBER = theme.qc("#f0a54a")
TEXT = theme.qc("#eceef4")
MUTED = theme.qc("#8b8d9c")
FAINT = theme.qc("#5c5e6c")
CARD = theme.qc("#1b1d27")
BORDER = theme.qc("#2b2e3b")

DEMO_TEXT = "Running ten minutes late, start without me."

# Timeline of one loop, in seconds.
_KEY_DOWN = 0.7
_KEY_UP = 3.0
_TYPED = 3.9
_TYPING_END = 5.6
_LOOP = 7.6


def _ease(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return 1 - (1 - t) ** 3


class DemoScene(QWidget):
    """The painted animation: a chat box, the hotkey and the recording pill."""

    def __init__(self, key_label: str) -> None:
        super().__init__()
        self.key_label = key_label
        self.setMinimumSize(520, 250)
        self._started = time.monotonic()
        self._animate = animations_enabled()
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self.update)
        if self._animate:
            self._timer.start()

    def _t(self) -> float:
        if not self._animate:
            # A still picture of the result for people with animations off.
            return _TYPING_END + 0.3
        return (time.monotonic() - self._started) % _LOOP

    def paintEvent(self, event) -> None:  # noqa: N802, ANN001
        t = self._t()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        w = self.width()
        self._draw_chat(painter, t, QRectF(30, 14, w - 60, 112))
        key_down = _KEY_DOWN <= t < _KEY_UP
        self._draw_key(painter, key_down, QPointF(w / 2, 214))
        self._draw_pill(painter, t, QPointF(w / 2, 158))

    # -- pieces -------------------------------------------------------------

    def _draw_chat(self, p: QPainter, t: float, rect: QRectF) -> None:
        p.setPen(QPen(BORDER, 1))
        p.setBrush(CARD)
        p.drawRoundedRect(rect, 12, 12)
        # Title bar dots, so it reads as "some other app".
        for i, color in enumerate(("#f0546b", "#f0a54a", "#3ecf8e")):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(color))
            p.drawEllipse(QPointF(rect.left() + 18 + i * 14, rect.top() + 16), 4, 4)
        p.setPen(FAINT)
        p.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
        p.drawText(QRectF(rect.left(), rect.top() + 8, rect.width(), 16), Qt.AlignCenter, "Chat")

        box = QRectF(rect.left() + 16, rect.bottom() - 52, rect.width() - 32, 38)
        p.setPen(QPen(theme.qc("#3a3d4c"), 1))
        p.setBrush(theme.qc("#14151c"))
        p.drawRoundedRect(box, 9, 9)

        if t < _TYPED:
            shown = ""
        elif t < _TYPING_END:
            shown = DEMO_TEXT[: int(len(DEMO_TEXT) * (t - _TYPED) / (_TYPING_END - _TYPED))]
        else:
            shown = DEMO_TEXT
        fade = 1.0
        if self._animate and t > _LOOP - 0.6:
            fade = max(0.0, (_LOOP - t) / 0.6)  # clears before the next loop
        font = QFont("Segoe UI", 10)
        p.setFont(font)
        color = QColor(TEXT)
        color.setAlphaF(fade)
        p.setPen(color)
        text_rect = box.adjusted(14, 0, -14, 0)
        if shown:
            p.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, shown)
        else:
            placeholder = QColor(FAINT)
            p.setPen(placeholder)
            p.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, "Message")
        # Blinking caret after the text.
        if (t * 2) % 2 < 1.2 or _TYPED <= t < _TYPING_END:
            advance = QFontMetricsF(font).horizontalAdvance(shown) if shown else 0
            x = text_rect.left() + advance + 2
            caret = QColor(ACCENT)
            caret.setAlphaF(fade if shown else 1.0)
            p.setPen(QPen(caret, 1.6))
            p.drawLine(QPointF(x, box.center().y() - 9), QPointF(x, box.center().y() + 9))

    def _draw_key(self, p: QPainter, down: bool, center: QPointF) -> None:
        p.setFont(QFont("Segoe UI", 11, QFont.Bold))
        label_w = QFontMetricsF(p.font()).horizontalAdvance(self.key_label)
        width = max(58.0, label_w + 30)
        press = 3.0 if down else 0.0
        base = QRectF(center.x() - width / 2, center.y() - 20, width, 40)
        # Key side (the part you see under the cap).
        p.setPen(Qt.NoPen)
        p.setBrush(theme.qc("#0d0e13"))
        p.drawRoundedRect(base.translated(0, 4), 9, 9)
        cap = base.translated(0, press)
        grad = QLinearGradient(cap.topLeft(), cap.bottomLeft())
        if down:
            grad.setColorAt(0, theme.qc("#2a4d3d"))
            grad.setColorAt(1, theme.qc("#21392f"))
        else:
            grad.setColorAt(0, theme.qc("#2b2e3b"))
            grad.setColorAt(1, theme.qc("#22242f"))
        p.setBrush(grad)
        p.setPen(QPen(ACCENT if down else theme.qc("#3a3d4c"), 1.2))
        p.drawRoundedRect(cap, 9, 9)
        p.setPen(ACCENT if down else TEXT)
        p.drawText(cap, Qt.AlignCenter, self.key_label)
        p.setPen(FAINT)
        p.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
        p.drawText(
            QRectF(base.right() + 12, base.top(), 120, base.height()),
            Qt.AlignVCenter | Qt.AlignLeft,
            "hold" if down else "",
        )

    def _draw_pill(self, p: QPainter, t: float, center: QPointF) -> None:
        if t < _KEY_DOWN or t > _TYPED + 1.4:
            return
        appear = _ease((t - _KEY_DOWN) / 0.18)
        leave = 1.0 - _ease((t - (_TYPED + 1.1)) / 0.3) if t > _TYPED + 1.1 else 1.0
        alpha = appear * leave
        if t < _KEY_UP:
            state, color, label = "recording", ACCENT, "Recording"
        elif t < _TYPED:
            state, color, label = "transcribing", AMBER, "Transcribing"
        else:
            state, color, label = "typed", ACCENT, "Typed"

        width = 190 if state != "typed" else 112
        rect = QRectF(center.x() - width / 2, center.y() - 17 + (1 - appear) * 8, width, 34)
        p.setOpacity(alpha)
        p.setPen(QPen(QColor(255, 255, 255, 26), 1))
        p.setBrush(QColor(24, 25, 33, 245))
        p.drawRoundedRect(rect, 17, 17)

        dot = QPointF(rect.left() + 20, rect.center().y())
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        if state == "typed":
            p.drawEllipse(dot, 7, 7)
            pen = QPen(theme.qc("#14151c"), 1.8)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen)
            p.drawPolyline(
                [dot + QPointF(-3.2, 0.2), dot + QPointF(-0.8, 2.6), dot + QPointF(3.4, -2.4)]
            )
        else:
            glow = QColor(color)
            glow.setAlpha(80)
            p.setBrush(glow)
            p.drawEllipse(dot, 7, 7)
            p.setBrush(color)
            p.drawEllipse(dot, 3.6, 3.6)

        p.setPen(TEXT)
        p.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        p.drawText(
            QRectF(rect.left() + 36, rect.top(), 100, rect.height()),
            Qt.AlignVCenter | Qt.AlignLeft,
            label,
        )
        if state != "typed":
            bars_left = rect.right() - 66
            for i in range(11):
                if state == "recording":
                    # A made-up voice: words of different loudness with gaps.
                    voice = abs(math.sin(t * 7.3 + i * 0.5)) * (0.55 + 0.45 * math.sin(t * 2.1))
                    value = max(0.08, voice * (0.4 + 0.6 * i / 10))
                else:
                    value = 0.2 + 0.3 * (0.5 + 0.5 * math.sin(t * 6 - i * 0.65))
                h = 3 + value * 16
                bar_color = QColor(color)
                bar_color.setAlpha(120 + int(135 * i / 10) if state == "recording" else 210)
                p.setPen(Qt.NoPen)
                p.setBrush(bar_color)
                p.drawRoundedRect(
                    QRectF(bars_left + i * 5, rect.center().y() - h / 2, 3, h), 1.5, 1.5
                )
        p.setOpacity(1.0)


class WelcomeDialog(QDialog):
    """The welcome window around the demo, with the three steps spelled out."""

    def __init__(self, hotkey: str, stylesheet: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        key_label = hotkey.title() if len(hotkey) > 3 else hotkey.upper()
        self.setWindowTitle("Welcome to VoxScribe")
        self.setStyleSheet(stylesheet)
        self.setMinimumWidth(600)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 22)
        layout.setSpacing(10)

        title = QLabel("Welcome to VoxScribe")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #eceef4;")
        layout.addWidget(title)
        intro = QLabel(
            f"Hold <b>{key_label}</b> in any app, talk, then let go. Your words are typed "
            "where your cursor is. Everything runs on this PC."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("font-size: 13px; color: #8b8d9c;")
        layout.addWidget(intro)

        layout.addWidget(DemoScene(key_label))

        steps = QHBoxLayout()
        steps.setSpacing(10)
        for number, text in (
            ("1", f"Hold {key_label}"),
            ("2", "Talk normally"),
            ("3", "Let go to type"),
        ):
            step = QLabel(
                f"<span style='color:#3ecf8e; font-weight:800;'>{number}</span>&nbsp;&nbsp;{text}"
            )
            step.setStyleSheet(
                "background: #1b1d27; border: 1px solid #242631; border-radius: 10px;"
                "padding: 9px 12px; color: #eceef4; font-size: 12px; font-weight: 600;"
            )
            steps.addWidget(step, 1)
        layout.addLayout(steps)

        note = QLabel(
            "VoxScribe waits in the system tray (bottom right, near the clock). "
            "Change the key, language and more in Settings. The first time, the speech "
            "model downloads once in the background."
        )
        note.setWordWrap(True)
        note.setStyleSheet("font-size: 11px; color: #5c5e6c;")
        layout.addWidget(note)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.open_button = QPushButton("Open VoxScribe")
        self.open_button.setStyleSheet(
            "QPushButton { background: #1b1d27; color: #eceef4; border: 1px solid #2b2e3b;"
            " border-radius: 9px; padding: 8px 18px; font-weight: 600; }"
            "QPushButton:hover { background: #22242f; }"
        )
        got_it = QPushButton("Got it")
        got_it.setStyleSheet(
            "QPushButton { background: #3ecf8e; color: #0b2418; border: none;"
            " border-radius: 9px; padding: 8px 22px; font-weight: 700; }"
            "QPushButton:hover { background: #4ee0a0; }"
        )
        got_it.setDefault(True)
        for button in (self.open_button, got_it):
            button.setCursor(Qt.PointingHandCursor)
            button.setMinimumHeight(36)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        got_it.clicked.connect(self.accept)
        self.open_button.clicked.connect(lambda: self.done(2))
