"""One-off script: generates docs/favicon assets and docs/og-image.png,
matching the landing page's dark/violet-cyan-magenta gradient identity.

Run with: venv\\Scripts\\python.exe scripts\\generate_web_assets.py
"""
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import QApplication

ACCENT = "#8b7cf6"
ACCENT_HOVER = "#a996ff"
ACCENT_PRESSED = "#6a5cd6"
CYAN = "#22d3ee"
MAGENTA = "#e879f9"
BG = "#06060f"


def draw_mic_badge(painter: QPainter, x: float, y: float, size: float) -> None:
    """Draws the same violet mic badge used as the app icon / nav brand mark."""
    bg = QLinearGradient(QPointF(x, y), QPointF(x, y + size))
    bg.setColorAt(0.0, QColor("#9d90f8"))
    bg.setColorAt(1.0, QColor(ACCENT_PRESSED))
    fg = QColor("#ffffff")

    painter.setBrush(QBrush(bg))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(QRectF(x, y, size, size))

    body_w = size * 0.28
    body_h = size * 0.42
    body_x = x + (size - body_w) / 2
    body_y = y + size * 0.16
    painter.setBrush(QBrush(fg))
    painter.drawRoundedRect(QRectF(body_x, body_y, body_w, body_h), body_w / 2, body_w / 2)

    pen = QPen(fg)
    pen.setWidthF(size * 0.045)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    stand_rect = QRectF(x + size * 0.28, y + size * 0.42, size * 0.44, size * 0.36)
    painter.drawArc(stand_rect, 0, -180 * 16)
    painter.drawLine(
        int(x + size * 0.5), int(y + size * 0.60), int(x + size * 0.5), int(y + size * 0.78)
    )
    painter.drawLine(
        int(x + size * 0.36), int(y + size * 0.78), int(x + size * 0.64), int(y + size * 0.78)
    )


def make_favicon(size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    draw_mic_badge(painter, 0, 0, size)
    painter.end()
    return pm


def make_og_image() -> QPixmap:
    w, h = 1200, 630
    pm = QPixmap(w, h)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)

    # Base background
    painter.fillRect(0, 0, w, h, QColor(BG))

    # Ambient glow blobs, matching the hero's purple/cyan/magenta field
    def glow(cx: float, cy: float, r: float, color: str, alpha: int) -> None:
        grad = QRadialGradient(QPointF(cx, cy), r)
        c1 = QColor(color)
        c1.setAlpha(alpha)
        c2 = QColor(color)
        c2.setAlpha(0)
        grad.setColorAt(0.0, c1)
        grad.setColorAt(1.0, c2)
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), r, r)

    glow(180, 120, 380, ACCENT, 130)
    glow(1040, 500, 360, CYAN, 90)
    glow(950, 80, 260, MAGENTA, 70)

    # Mic badge
    badge_size = 120
    draw_mic_badge(painter, 90, 90, badge_size)

    # Brand wordmark next to badge
    painter.setPen(QColor("#f3f3fb"))
    font = QFont("Segoe UI", 34, QFont.Bold)
    painter.setFont(font)
    painter.drawText(QRectF(90 + badge_size + 24, 90, 500, badge_size), Qt.AlignVCenter | Qt.AlignLeft, "VoxScribe")

    # Headline
    headline_font = QFont("Segoe UI", 54, QFont.Bold)
    painter.setFont(headline_font)
    painter.setPen(QColor("#f3f3fb"))
    painter.drawText(QRectF(90, 270, 1020, 130), Qt.AlignLeft | Qt.TextWordWrap, "Talk anywhere on Windows.")

    grad_text = QLinearGradient(QPointF(90, 0), QPointF(700, 0))
    grad_text.setColorAt(0.0, QColor(ACCENT_HOVER))
    grad_text.setColorAt(0.5, QColor(CYAN))
    grad_text.setColorAt(1.0, QColor(MAGENTA))
    painter.setPen(QPen(QBrush(grad_text), 0))
    painter.drawText(QRectF(90, 340, 1020, 90), Qt.AlignLeft, "VoxScribe types it for you.")

    # Subhead / stats line
    painter.setPen(QColor("#9797ac"))
    sub_font = QFont("Segoe UI", 22)
    painter.setFont(sub_font)
    painter.drawText(
        QRectF(90, 460, 1020, 60),
        Qt.AlignLeft,
        "Free · 100% local transcription · Open source (MIT) · Windows 10/11",
    )

    painter.end()
    return pm


def main() -> None:
    app = QApplication(sys.argv)  # noqa: F841 -- required for QPixmap/QPainter to work

    out_dir = Path(__file__).parent.parent / "docs"
    out_dir.mkdir(exist_ok=True)

    make_favicon(32).save(str(out_dir / "favicon-32.png"), "PNG")
    make_favicon(16).save(str(out_dir / "favicon-16.png"), "PNG")
    make_favicon(180).save(str(out_dir / "apple-touch-icon.png"), "PNG")
    make_favicon(256).save(str(out_dir / "favicon.ico"), "ICO")
    make_og_image().save(str(out_dir / "og-image.png"), "PNG")

    print(f"Saved favicon-32.png, favicon-16.png, apple-touch-icon.png, favicon.ico, og-image.png to {out_dir}")


if __name__ == "__main__":
    main()
