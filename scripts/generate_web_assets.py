"""One-off script: generates docs/favicon assets and docs/og-image.png,
matching the landing page's dark/emerald-teal waveform mark.

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

ACCENT = "#10b981"
ACCENT_HOVER = "#34d399"
ACCENT_PRESSED = "#059669"
CYAN = "#5eead4"
BG = "#06060f"


def draw_wave_mark(painter: QPainter, x: float, y: float, size: float) -> None:
    """Draws the V-shaped soundwave mark used as the nav brand mark: five
    gradient bars, tall-to-short-to-tall, reading as both a waveform and a
    'V' monogram for VoxScribe."""
    grad = QLinearGradient(QPointF(x, y), QPointF(x + size, y + size))
    grad.setColorAt(0.0, QColor(ACCENT))
    grad.setColorAt(0.55, QColor(ACCENT_HOVER))
    grad.setColorAt(1.0, QColor(CYAN))
    painter.setBrush(QBrush(grad))
    painter.setPen(Qt.NoPen)

    bar_w = size * 0.11
    gap = size * 0.115
    bottom = y + size * 0.82
    heights = [0.62, 0.42, 0.24, 0.42, 0.62]
    for i, h_frac in enumerate(heights):
        bar_h = size * h_frac
        bar_x = x + size * 0.06 + i * (bar_w + gap)
        bar_y = bottom - bar_h
        painter.drawRoundedRect(
            QRectF(bar_x, bar_y, bar_w, bar_h), bar_w / 2, bar_w / 2
        )


def make_favicon(size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    draw_wave_mark(painter, 0, 0, size)
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
    glow(950, 80, 260, ACCENT_HOVER, 70)

    # Wave mark
    badge_size = 120
    draw_wave_mark(painter, 90, 90, badge_size)

    # Brand wordmark next to badge
    painter.setPen(QColor("#f3f3fb"))
    font = QFont("Segoe UI", 34, QFont.Bold)
    painter.setFont(font)
    wordmark_rect = QRectF(90 + badge_size + 24, 90, 500, badge_size)
    painter.drawText(wordmark_rect, Qt.AlignVCenter | Qt.AlignLeft, "VoxScribe")

    # Headline
    headline_font = QFont("Segoe UI", 54, QFont.Bold)
    painter.setFont(headline_font)
    painter.setPen(QColor("#f3f3fb"))
    headline_rect = QRectF(90, 270, 1020, 130)
    painter.drawText(headline_rect, Qt.AlignLeft | Qt.TextWordWrap, "Talk anywhere on Windows.")

    grad_text = QLinearGradient(QPointF(90, 0), QPointF(700, 0))
    grad_text.setColorAt(0.0, QColor(ACCENT))
    grad_text.setColorAt(0.5, QColor(ACCENT_HOVER))
    grad_text.setColorAt(1.0, QColor(CYAN))
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

    print(f"Saved favicon-32.png, favicon-16.png, apple-touch-icon.png, favicon.ico, "
          f"og-image.png to {out_dir}")


if __name__ == "__main__":
    main()
