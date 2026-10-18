"""Small floating status indicator, shown only while recording/transcribing.

This is the "Wispr Flow" style pill: a frameless, always-on-top, translucent
widget with a status icon, a short status word and, while recording, a live
mic level. It has no buttons and no window chrome -- MainWindow stays the
"home base" window the user doesn't need to keep open, while this pill is
what's actually visible while dictating into some other app via the global
hotkey.

States:
- recording: green dot and a scrolling level meter fed from the mic callback
  (feed_audio), so the user can see the mic is really hearing them. Matters
  most on the quiet Bluetooth headsets this app was built on.
- transcribing: amber dot that breathes and a slow wave through the bars.
- flash_success / flash_error: a check mark or a red "!" with a short
  shake, then the pill hides itself.
All motion except the level meter itself is dropped when Windows' "Show
animations in Windows" setting is off (the level is information, not
decoration).
"""

from __future__ import annotations

import math
import time
from collections import deque

import numpy as np
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QWidget,
)

from app.motion import animations_enabled as _animations_enabled
from core.audio_capture import chunk_level

_MIN_WIDTH = 150
_HEIGHT = 42
_MARGIN_BOTTOM = 64  # distance from the bottom of the screen
_TICK_MS = 33  # ~30 fps, only while the pill is visible

_GREEN = "#3ecf8e"
_AMBER = "#f0a54a"
_RED = "#f0546b"

# Slightly richer / more saturated than the in-window status colors so the
# dot pops against the dark pill from a glance-distance.
_DOT_COLORS = {
    "recording": _GREEN,
    "transcribing": _AMBER,
    "not_ready": _RED,
    "model_failed": _RED,
    "busy": _AMBER,
    "redo": _AMBER,
}
_LABELS = {
    "recording": "Recording",
    "transcribing": "Transcribing",
    "not_ready": "Still loading model...",
    "model_failed": "Model failed to load",
    "busy": "Busy with file import",
    "redo": "Trying harder",
}

_BAR_COUNT = 11
_SHAKE_SECONDS = 0.36
_ENTER_SECONDS = 0.16
_LEAVE_SECONDS = 0.18
_SLIDE_PX = 8
_CHECK_SECONDS = 0.22


class _StatusIcon(QWidget):
    """The pill's left icon: a glowing dot, a check mark or a red "!"."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self.mode = "dot"  # "dot" | "check" | "error"
        self.color = QColor(_GREEN)
        self.glow = 1.0  # halo strength, animated while transcribing
        self.progress = 1.0  # how much of the check mark is drawn

    def paintEvent(self, event) -> None:  # noqa: N802, ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)

        rect = QRectF(self.rect())
        center = rect.center()

        # Soft halo.
        glow = QRadialGradient(center, rect.width() / 2)
        halo_color = QColor(self.color)
        halo_color.setAlpha(int(110 * self.glow))
        glow.setColorAt(0.0, halo_color)
        transparent = QColor(self.color)
        transparent.setAlpha(0)
        glow.setColorAt(1.0, transparent)
        painter.setBrush(glow)
        painter.drawEllipse(rect)

        if self.mode == "dot":
            core_size = rect.width() * 0.5
            core_rect = QRectF(0, 0, core_size, core_size)
            core_rect.moveCenter(center)
            painter.setBrush(self.color)
            painter.drawEllipse(core_rect)
            return

        # Check and error both sit on a solid disc.
        disc = QRectF(0, 0, rect.width() * 0.86, rect.height() * 0.86)
        disc.moveCenter(center)
        painter.setBrush(self.color)
        painter.drawEllipse(disc)

        pen = QPen(QColor("#14151c"), 1.9)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        w = rect.width()
        if self.mode == "check":
            points = [QPointF(w * 0.30, w * 0.52), QPointF(w * 0.44, w * 0.66),
                      QPointF(w * 0.71, w * 0.37)]
            path = QPainterPath(points[0])
            path.lineTo(points[1])
            path.lineTo(points[2])
            if self.progress < 1.0:
                # Draw only the first part of the stroke so it "writes" itself.
                partial = QPainterPath(points[0])
                steps = 12
                for i in range(1, steps + 1):
                    partial.lineTo(path.pointAtPercent(self.progress * i / steps))
                path = partial
            painter.drawPath(path)
        else:
            painter.drawLine(QPointF(w / 2, w * 0.30), QPointF(w / 2, w * 0.56))
            painter.drawPoint(QPointF(w / 2, w * 0.70))


class _LevelBars(QWidget):
    """A row of thin bars: a scrolling mic level while recording (newest on
    the right, older bars fading out to the left), or a slow travelling wave
    while transcribing."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(_BAR_COUNT * 5, 22)
        self.mode = "level"  # "level" | "working"
        self.color = QColor(_GREEN)
        self.levels: deque[float] = deque([0.0] * _BAR_COUNT, maxlen=_BAR_COUNT)
        self.phase = 0.0

    def paintEvent(self, event) -> None:  # noqa: N802, ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)

        h = self.height()
        bar_w = 3.0
        step = self.width() / _BAR_COUNT
        min_h = 3.0
        for i in range(_BAR_COUNT):
            if self.mode == "level":
                value = self.levels[i]
                alpha = 110 + int(145 * i / (_BAR_COUNT - 1))
            else:
                value = 0.18 + 0.32 * (0.5 + 0.5 * math.sin(self.phase - i * 0.65))
                alpha = 200
            bar_h = min_h + value * (h - min_h)
            color = QColor(self.color)
            color.setAlpha(alpha)
            painter.setBrush(color)
            x = i * step + (step - bar_w) / 2
            painter.drawRoundedRect(
                QRectF(x, (h - bar_h) / 2, bar_w, bar_h), bar_w / 2, bar_w / 2
            )


class FloatingIndicator(QWidget):
    """Borderless, always-on-top pill showing recording/transcribing status."""

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool,
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.resize(_MIN_WIDTH, _HEIGHT)

        # Drop shadow lifts the pill off whatever's underneath it (video
        # calls, dark editors, light documents, etc.) so it reads as a
        # floating object rather than a flat sticker.
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 160))
        self.setGraphicsEffect(shadow)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 9, 16, 9)
        layout.setSpacing(10)

        self._icon = _StatusIcon(self)
        layout.addWidget(self._icon)

        self._label = QLabel(_LABELS["recording"])
        self._label.setStyleSheet(
            "color: #f1f2f8; font-size: 12px; font-weight: 600; "
            'font-family: "Segoe UI";'
        )
        layout.addWidget(self._label, stretch=1)

        self._bars = _LevelBars(self)
        layout.addWidget(self._bars)

        self._kind = ""
        self._animate = True
        # Written from the audio callback thread, read and reset on the Qt
        # thread each tick. A lost update only costs one frame of the meter.
        self._pending_level = 0.0
        self._smoothed_level = 0.0
        self._base_pos = QPoint(0, 0)
        self._shake_started: float | None = None
        self._check_started: float | None = None
        self._started = time.monotonic()
        self._enter_started: float | None = None
        self._leave_started: float | None = None

        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(_TICK_MS)
        self._tick_timer.timeout.connect(self._tick)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide_indicator)

        self._position_bottom_center()
        self.hide()

    def _position_bottom_center(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + geo.height() - self.height() - _MARGIN_BOTTOM
        self._base_pos = QPoint(x, y)
        self._place()

    def paintEvent(self, event) -> None:  # noqa: N802, ANN001
        # Rounded, semi-transparent dark pill with a subtle top-to-bottom
        # gradient and a faint 1px light border, behind the icon + label.
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = QRectF(self.rect())
        radius = rect.height() / 2

        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        gradient.setColorAt(0.0, QColor(34, 35, 46, 235))
        gradient.setColorAt(1.0, QColor(20, 21, 28, 235))

        painter.setPen(Qt.NoPen)
        painter.setBrush(gradient)
        painter.drawRoundedRect(rect, radius, radius)

        border_rect = rect.adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QColor(255, 255, 255, 26))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(border_rect, radius, radius)

    # -- public API -------------------------------------------------------

    def feed_audio(self, chunk: np.ndarray) -> None:
        """Called from the mic callback thread with each captured chunk."""
        if self._kind != "recording":
            return
        level = chunk_level(chunk)
        if level > self._pending_level:
            self._pending_level = level

    def show_status(self, kind: str, detail: str = "") -> None:
        """Show the pill with the given status ('recording', 'transcribing',
        one of the other _LABELS keys, or any short text). `detail` is added
        after the label, for example the dictation mode in use."""
        self._hide_timer.stop()
        self._shake_started = None
        self._check_started = None
        if kind == "recording" and self._kind != "recording":
            self._bars.levels.extend([0.0] * _BAR_COUNT)
            self._smoothed_level = 0.0
            self._pending_level = 0.0
        self._kind = kind
        color = _DOT_COLORS.get(kind, _GREEN)
        self._icon.mode = "dot"
        self._icon.color = QColor(color)
        self._icon.glow = 1.0
        self._icon.progress = 1.0
        self._bars.setVisible(kind in ("recording", "transcribing", "redo"))
        self._bars.mode = "level" if kind == "recording" else "working"
        self._bars.color = QColor(color)
        label = _LABELS.get(kind, kind)
        self._show_with_text(f"{label} \u00b7 {detail}" if detail else label)

    def flash_success(self, text: str = "Typed", ms: int = 900) -> None:
        """A check mark that draws itself, then the pill hides."""
        if self._flash("check", _GREEN, text, ms):
            self._check_started = time.monotonic() if self._animate else None

    def flash_error(self, text: str, ms: int = 2200) -> None:
        """A red "!" and a short sideways shake, then the pill hides."""
        if self._flash("error", _RED, text, ms):
            self._shake_started = time.monotonic() if self._animate else None

    def hide_indicator(self) -> None:
        """Fades and slides the pill away (or hides it at once with
        animations off). Showing a new status meanwhile cancels the fade."""
        self._hide_timer.stop()
        self._kind = ""
        if self.isVisible() and _animations_enabled():
            if self._leave_started is None:
                self._leave_started = time.monotonic()
                self._enter_started = None
                if not self._tick_timer.isActive():
                    self._tick_timer.start()
            return
        self._finish_hide()

    def _finish_hide(self) -> None:
        self._tick_timer.stop()
        self._leave_started = None
        self._enter_started = None
        self.hide()
        self.setWindowOpacity(1.0)

    # -- internals --------------------------------------------------------

    def _flash(self, mode: str, color: str, text: str, ms: int) -> bool:
        if self._kind == "recording":
            # The result of the previous dictation arrived after a new one
            # had already started; the live recording state wins.
            return False
        self._animate = _animations_enabled()
        self._kind = mode
        self._shake_started = None
        self._check_started = None
        self._icon.mode = mode
        self._icon.color = QColor(color)
        self._icon.glow = 1.0
        self._icon.progress = 1.0 if mode != "check" or not self._animate else 0.0
        self._bars.hide()
        # Sized to the message, so a short "Typed" isn't a half-empty pill.
        self._show_with_text(text, min_width=0)
        self._hide_timer.start(ms)
        return True

    def _show_with_text(self, text: str, min_width: int = _MIN_WIDTH) -> None:
        self._animate = _animations_enabled()
        self._label.setText(text)
        self.layout().activate()  # pick up the bars being shown or hidden
        self.resize(max(min_width, self.layout().sizeHint().width()), _HEIGHT)
        self._position_bottom_center()
        self._icon.update()
        self._bars.update()
        appearing = not self.isVisible() or self._leave_started is not None
        self._leave_started = None
        if appearing and self._animate:
            # Rises a few pixels and fades in, rather than popping into place.
            self._enter_started = time.monotonic()
            self.setWindowOpacity(0.0)
            self._place()
        elif appearing:
            self.setWindowOpacity(1.0)
        self.show()
        self.raise_()
        if not self._tick_timer.isActive():
            self._tick_timer.start()

    def _tick(self) -> None:
        now = time.monotonic()
        if self._kind == "recording":
            target = self._pending_level
            self._pending_level = 0.0
            if target > self._smoothed_level:
                self._smoothed_level += (target - self._smoothed_level) * 0.6
            else:
                self._smoothed_level = self._smoothed_level * 0.78 + target * 0.22
            self._bars.levels.append(self._smoothed_level)
            self._bars.update()
        elif self._kind in ("transcribing", "redo"):
            if self._animate:
                self._bars.phase += 0.2
                self._icon.glow = 0.55 + 0.45 * math.sin((now - self._started) * 4.0)
                self._bars.update()
                self._icon.update()
        if self._check_started is not None:
            progress = min(1.0, (now - self._check_started) / _CHECK_SECONDS)
            self._icon.progress = progress
            self._icon.update()
            if progress >= 1.0:
                self._check_started = None
        if self._shake_started is not None and now - self._shake_started >= _SHAKE_SECONDS:
            self._shake_started = None
        if self._enter_started is not None:
            t = min(1.0, (now - self._enter_started) / _ENTER_SECONDS)
            self.setWindowOpacity(1 - (1 - t) ** 3)
            if t >= 1.0:
                self._enter_started = None
        if self._leave_started is not None:
            t = min(1.0, (now - self._leave_started) / _LEAVE_SECONDS)
            self.setWindowOpacity(1 - t * t)
            if t >= 1.0:
                self._finish_hide()
                return
        self._place()

    def _place(self) -> None:
        """Moves the pill to its base spot plus any slide or shake offset."""
        now = time.monotonic()
        dx = dy = 0
        if self._shake_started is not None:
            elapsed = now - self._shake_started
            decay = max(0.0, 1.0 - elapsed / _SHAKE_SECONDS)
            dx = int(round(7 * decay * math.sin(elapsed * 2 * math.pi * 11)))
        if self._enter_started is not None:
            t = min(1.0, (now - self._enter_started) / _ENTER_SECONDS)
            dy = int(round(_SLIDE_PX * (1 - t) ** 3))
        elif self._leave_started is not None:
            t = min(1.0, (now - self._leave_started) / _LEAVE_SECONDS)
            dy = int(round(_SLIDE_PX * 0.75 * t * t))
        target = self._base_pos + QPoint(dx, dy)
        if self.pos() != target:
            self.move(target)
