"""One-off script: generates app/icon.ico, a simple microphone glyph.

Run with: venv\\Scripts\\python.exe scripts\\generate_icon.py
"""
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import QApplication


def draw_mic_pixmap(size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)

    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)

    # Violet gradient to match the app's dark/violet theme, rather than a
    # flat blue circle -- gives the icon a touch of depth at small sizes.
    bg = QLinearGradient(QPointF(0, 0), QPointF(0, size))
    bg.setColorAt(0.0, QColor("#9d90f8"))
    bg.setColorAt(1.0, QColor("#6a5cd6"))
    fg = QColor("#ffffff")

    painter.setBrush(QBrush(bg))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(0, 0, size, size)

    # Mic capsule (body)
    body_w = size * 0.28
    body_h = size * 0.42
    body_x = (size - body_w) / 2
    body_y = size * 0.16
    painter.setBrush(QBrush(fg))
    painter.drawRoundedRect(QRectF(body_x, body_y, body_w, body_h), body_w / 2, body_w / 2)

    # Stand (arc-ish U shape) + base line, drawn with a thick pen
    pen = painter.pen()
    pen.setColor(fg)
    pen.setWidthF(size * 0.045)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    stand_rect = QRectF(size * 0.28, size * 0.42, size * 0.44, size * 0.36)
    painter.drawArc(stand_rect, 0, -180 * 16)

    # Vertical line from stand down to base
    painter.drawLine(int(size * 0.5), int(size * 0.60), int(size * 0.5), int(size * 0.78))
    # Base line
    painter.drawLine(int(size * 0.36), int(size * 0.78), int(size * 0.64), int(size * 0.78))

    painter.end()
    return pm


def main() -> None:
    app = QApplication(sys.argv)  # noqa: F841 -- required for QPixmap/QPainter to work
    icon = QIcon()
    for size in (16, 32, 48, 64, 128, 256):
        icon.addPixmap(draw_mic_pixmap(size))

    out_dir = Path(__file__).parent.parent / "app"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "icon.ico"

    # QIcon has no direct multi-size .ico writer; save the largest pixmap,
    # Qt's .ico image writer plugin will produce a valid single/multi-image
    # ICO from repeated calls is not supported, so save the biggest size --
    # good enough for taskbar/title bar/PyInstaller use.
    draw_mic_pixmap(256).save(str(out_path), "ICO")
    print(f"Saved icon to {out_path}")


if __name__ == "__main__":
    main()
