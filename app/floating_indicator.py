"""Small floating status indicator, shown only while recording/transcribing.

This is the "Wispr Flow" style pill: a frameless, always-on-top, translucent
widget with a colored dot and a short status word. It has no buttons and no
window chrome -- MainWindow stays the "home base" window the user doesn't
need to keep open, while this pill is what's actually visible while
dictating into some other app via the global hotkey.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QRadialGradient
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QWidget,
)

_WIDTH = 160
_HEIGHT = 42
_MARGIN_BOTTOM = 64  # distance from the bottom of the screen

# Slightly richer / more saturated than the in-window status colors so the
# dot pops against the dark pill from a glance-distance.
_DOT_COLORS = {
    "recording": "#3ecf8e",  # green
    "transcribing": "#f0a54a",  # amber
    "not_ready": "#f0546b",  # red
}
_LABELS = {
    "recording": "Recording...",
    "transcribing": "Transcribing...",
    "not_ready": "Still loading model...",
}


class _Dot(QWidget):
    """A small glowing circle: a soft radial halo behind a solid core,
    repainted whenever its color changes."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self._color = QColor(_DOT_COLORS["recording"])

    def set_color(self, hex_color: str) -> None:
        self._color = QColor(hex_color)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802, ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)

        rect = QRectF(self.rect())
        center = rect.center()

        # Soft halo.
        glow = QRadialGradient(center, rect.width() / 2)
        halo_color = QColor(self._color)
        halo_color.setAlpha(110)
        glow.setColorAt(0.0, halo_color)
        transparent = QColor(self._color)
        transparent.setAlpha(0)
        glow.setColorAt(1.0, transparent)
        painter.setBrush(glow)
        painter.drawEllipse(rect)

        # Solid core.
        core_size = rect.width() * 0.5
        core_rect = QRectF(0, 0, core_size, core_size)
        core_rect.moveCenter(center)
        painter.setBrush(self._color)
        painter.drawEllipse(core_rect)


class FloatingIndicator(QWidget):
    """Borderless, always-on-top pill showing recording/transcribing status."""

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool,
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.resize(_WIDTH, _HEIGHT)

        # Drop shadow lifts the pill off whatever's underneath it (video
        # calls, dark editors, light documents, etc.) so it reads as a
        # floating object rather than a flat sticker.
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 160))
        self.setGraphicsEffect(shadow)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 9, 18, 9)
        layout.setSpacing(10)

        self._dot = _Dot(self)
        layout.addWidget(self._dot)

        self._label = QLabel(_LABELS["recording"])
        self._label.setStyleSheet(
            "color: #f1f2f8; font-size: 12px; font-weight: 600; "
            'font-family: "Segoe UI";'
        )
        layout.addWidget(self._label, stretch=1)

        self._position_bottom_center()
        self.hide()

    def _position_bottom_center(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + geo.height() - self.height() - _MARGIN_BOTTOM
        self.move(x, y)

    def paintEvent(self, event) -> None:  # noqa: N802, ANN001
        # Rounded, semi-transparent dark pill with a subtle top-to-bottom
        # gradient and a faint 1px light border, behind the dot + label.
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

    def show_status(self, kind: str) -> None:
        """Show the pill with the given status ('recording' or 'transcribing')."""
        self._dot.set_color(_DOT_COLORS.get(kind, _DOT_COLORS["recording"]))
        self._label.setText(_LABELS.get(kind, kind))
        self._position_bottom_center()
        self.show()
        self.raise_()

    def hide_indicator(self) -> None:
        self.hide()
