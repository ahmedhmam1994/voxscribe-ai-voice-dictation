"""One-off script: generates app/icon.ico (window, tray, installer and exe
icon) from the shared VoxScribe mark in scripts/brand_mark.py.

Run with: venv\\Scripts\\python.exe scripts\\generate_icon.py
"""
import io
import sys
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).parent))
from brand_mark import app_icon  # noqa: E402

SIZES = (16, 24, 32, 48, 64, 128, 256)


def to_pil(size: int, margin: float) -> Image.Image:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    app_icon(size, margin).save(buffer, "PNG")
    return Image.open(io.BytesIO(bytes(buffer.data()))).convert("RGBA")


def save_ico(path: Path, sizes=SIZES) -> None:
    """A real multi-size .ico: each size drawn on its own, so the 16 px tray
    icon stays sharp instead of being shrunk from 256. Small sizes get a
    thinner margin so the mark stays readable."""
    images = [to_pil(s, 0.12 if s <= 24 else 0.18) for s in sizes]
    images[-1].save(path, format="ICO", sizes=[(s, s) for s in sizes], append_images=images[:-1])


def main() -> None:
    app = QApplication(sys.argv)  # noqa: F841 -- required for QPixmap/QPainter
    out_path = Path(__file__).parent.parent / "app" / "icon.ico"
    save_ico(out_path)
    print(f"Saved icon to {out_path}")


if __name__ == "__main__":
    main()
