"""One-off script: generates app/icon.ico, a waveform glyph matching the
website's hero waveform visual.

Run with: venv\\Scripts\\python.exe scripts\\generate_icon.py
"""
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

# Relative bar heights (0-1 of the wave band) -- taller in the middle,
# tapering at the edges, like a real speech waveform rather than uniform bars.
_BAR_HEIGHTS = [0.25, 0.45, 0.7, 0.9, 1.0, 0.8, 0.55, 0.85, 1.0, 0.75, 0.4, 0.2]


def draw_wave_pixmap(size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)

    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)

    bg = QLinearGradient(QPointF(0, 0), QPointF(0, size))
    bg.setColorAt(0.0, QColor("#6ee7a0"))
    bg.setColorAt(1.0, QColor("#22a05a"))
    fg = QColor("#ffffff")

    painter.setBrush(QBrush(bg))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(0, 0, size, size)

    # Waveform bars, centered vertically, spanning most of the circle's width.
    band_top = size * 0.32
    band_height = size * 0.36
    band_center = band_top + band_height / 2
    margin = size * 0.16
    usable_width = size - 2 * margin
    n = len(_BAR_HEIGHTS)
    gap = usable_width * 0.12 / (n - 1)
    bar_w = (usable_width - gap * (n - 1)) / n

    painter.setBrush(QBrush(fg))
    painter.setPen(Qt.NoPen)
    for i, h_ratio in enumerate(_BAR_HEIGHTS):
        bar_h = band_height * h_ratio
        x = margin + i * (bar_w + gap)
        y = band_center - bar_h / 2
        radius = bar_w / 2
        painter.drawRoundedRect(QRectF(x, y, bar_w, bar_h), radius, radius)

    painter.end()
    return pm


def main() -> None:
    app = QApplication(sys.argv)  # noqa: F841 -- required for QPixmap/QPainter to work
    icon = QIcon()
    for size in (16, 32, 48, 64, 128, 256):
        icon.addPixmap(draw_wave_pixmap(size))

    out_dir = Path(__file__).parent.parent / "app"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "icon.ico"

    # QIcon has no direct multi-size .ico writer; save the largest pixmap,
    # Qt's .ico image writer plugin will produce a valid single/multi-image
    # ICO from repeated calls is not supported, so save the biggest size --
    # good enough for taskbar/title bar/PyInstaller use.
    draw_wave_pixmap(256).save(str(out_path), "ICO")
    print(f"Saved icon to {out_path}")


if __name__ == "__main__":
    main()
