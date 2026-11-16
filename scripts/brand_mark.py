"""The VoxScribe mark, shared by the icon and web asset scripts: three sound
bars that turn into a text cursor (voice becoming typed words).

The shapes are in the 108 unit grid of the Android launcher icon
(android/.../res/drawable/ic_launcher_foreground.xml); the mark itself spans
x 24 to 84 and y 26 to 82 of that grid. Keep the three in step.
"""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap

GREEN = "#3ECF8E"
TILE = "#121319"

# (x, y, width, height, corner radius) in the 108 grid.
_SHAPES = [
    (24, 44, 8, 20, 4),  # bars: 20, 36, 20 tall
    (38, 36, 8, 36, 4),
    (52, 44, 8, 20, 4),
    (70, 29, 7, 50, 0),  # cursor stem
    (63, 26, 21, 6, 3),  # cursor caps
    (63, 76, 21, 6, 3),
]
_LEFT, _TOP, _WIDTH, _HEIGHT = 24, 26, 60, 56


def draw_mark(painter: QPainter, x: float, y: float, size: float, color: str = GREEN) -> None:
    """Draws the mark centred in the square (x, y, size), filling its width
    or height, whichever is tighter."""
    scale = size / max(_WIDTH, _HEIGHT)
    left = x + (size - _WIDTH * scale) / 2
    top = y + (size - _HEIGHT * scale) / 2
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))
    for sx, sy, w, h, r in _SHAPES:
        rect = QRectF(left + (sx - _LEFT) * scale, top + (sy - _TOP) * scale, w * scale, h * scale)
        painter.drawRoundedRect(rect, r * scale, r * scale)


def app_icon(size: int, margin: float = 0.2) -> QPixmap:
    """The app icon: the mark on a dark rounded tile, as on Android. `margin`
    is the empty space around the mark on each side, as a share of `size`."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(TILE))
    radius = size * 0.24
    painter.drawRoundedRect(QRectF(0, 0, size, size), radius, radius)
    inner = size * (1 - 2 * margin)
    draw_mark(painter, size * margin, size * margin, inner)
    painter.end()
    return pm
