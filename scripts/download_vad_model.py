"""Download the Silero VAD ONNX model into core/models/.

The model file is git-ignored (binary asset, easily re-fetched), so run
this once after cloning / whenever core/models/silero_vad.onnx is missing.

Source: https://github.com/snakers4/silero-vad (MIT licensed)
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

MODEL_URL = "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"
DEST = Path(__file__).resolve().parent.parent / "core" / "models" / "silero_vad.onnx"


def main() -> None:
    DEST.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {MODEL_URL} -> {DEST}")
    urllib.request.urlretrieve(MODEL_URL, DEST)
    print(f"Done ({DEST.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
