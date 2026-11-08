"""Builds core/data/common_words.txt: the everyday lowercase words of the
Whisper token list, the same source the Android app reads (ScreenWords.common).

A word is kept when the tokenizer has it as one whole token after a space
("Ġhouse"), in plain a-z, at least two letters long. That gives about 20,000
ordinary words, and leaves names and rare terms out, which is the point:
core/learned_words.py never learns a fix to or from one of these words.

Run once after changing the rule; the output file is committed.

    venv\\Scripts\\python.exe scripts\\build_common_words.py [path\\to\\tokenizer.json]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "core" / "data" / "common_words.txt"


def find_tokenizer() -> Path:
    hub = Path.home() / ".cache" / "huggingface" / "hub"
    for path in sorted(hub.glob("models--Systran--faster-whisper-*/snapshots/*/tokenizer.json")):
        return path
    raise SystemExit("No Whisper tokenizer.json found; pass its path.")


def words_from(tokenizer: Path) -> list[str]:
    vocab = json.loads(tokenizer.read_text(encoding="utf-8"))["model"]["vocab"]
    found = set()
    for token in vocab:
        if not token.startswith("Ġ"):
            continue
        word = token[1:]
        if len(word) >= 2 and all("a" <= c <= "z" for c in word):
            found.add(word)
    return sorted(found)


def main() -> None:
    tokenizer = Path(sys.argv[1]) if len(sys.argv) > 1 else find_tokenizer()
    words = words_from(tokenizer)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        "# Everyday words from the Whisper token list. Built by scripts/build_common_words.py.\n"
        + "\n".join(words)
        + "\n",
        encoding="utf-8",
    )
    print(f"{len(words)} words -> {OUT}")


if __name__ == "__main__":
    main()
