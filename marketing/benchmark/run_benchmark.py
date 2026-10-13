"""Benchmark of the .srt import on a labeled sample clip.

Measures model load time, processing time for the clip, text accuracy against
the known script (with and without a custom vocabulary), and the structure of
the caption cards.

Run from the repo root:  venv\\Scripts\\python.exe marketing\\benchmark\\run_benchmark.py
"""

# ruff: noqa: E501
from __future__ import annotations

import difflib
import re
import sys
import time
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.version import __version__  # noqa: E402
from core.captions import review_flags, split_segments  # noqa: E402
from core.srt import format_srt  # noqa: E402
from core.transcribe import load_transcriber  # noqa: E402

HERE = Path(__file__).resolve().parent
CLIP = HERE / "sample_episode.wav"

REFERENCE = (
    "Hello and welcome to episode forty two. Today I am joined by Priya Raghunathan "
    "and Oluwaseun Adeyemi. Priya, you recently moved the whole platform to Kubernetes, "
    "and Oluwaseun, you rebuilt the PostgreSQL backups, so where did you both start, "
    "and what would you do differently if you had to begin again with only a small team, "
    "a tight budget, and a deadline that was already two weeks away? Well, the first thing "
    "we did was write down every service. Then we ranked them by risk. Great. The new "
    "release is version one point seven point two, and the Pro upgrade costs fourteen "
    "dollars. Thanks."
)
NAMES = ["Priya", "Raghunathan", "Oluwaseun", "Adeyemi", "Kubernetes", "PostgreSQL"]
VOCABULARY = "Priya Raghunathan, Oluwaseun Adeyemi, Kubernetes, PostgreSQL"


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def word_error_rate(reference: str, hypothesis: str) -> float:
    ref, hyp = words(reference), words(hypothesis)
    matcher = difflib.SequenceMatcher(a=ref, b=hyp, autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    return 1 - matched / max(1, len(ref))


def run(transcriber, prompt, label):
    start = time.perf_counter()
    segments = transcriber.transcribe_file_segments(str(CLIP), language="en", initial_prompt=prompt)
    seconds = time.perf_counter() - start
    text = " ".join(t for _s, _e, t in segments)
    cards = split_segments(segments, 42)
    srt = format_srt(cards)
    (HERE / f"sample_episode_{label}.srt").write_text(srt, encoding="utf-8")
    heard = [n for n in NAMES if n.lower() in text.lower()]
    flags = review_flags(cards)
    longest = max(
        (len(line) for _s, _e, t in cards for line in t.split("\n")), default=0
    )
    print(f"\n=== {label} ===")
    print(f"processing time: {seconds:.1f} s")
    print(f"segments from Whisper: {len(segments)}, caption cards: {len(cards)}")
    print(f"longest caption line: {longest} characters")
    print(f"word error rate against the script: {word_error_rate(REFERENCE, text) * 100:.1f}%")
    print(f"names and jargon heard right: {len(heard)} of {len(NAMES)} {heard}")
    print(f"missed: {[n for n in NAMES if n not in heard]}")
    print(f"review flags: {flags}")
    print("transcript:", text)
    print(srt)
    return seconds


def main() -> None:
    with wave.open(str(CLIP)) as wav:
        duration = wav.getnframes() / wav.getframerate()
    print(f"VoxScribe {__version__}, model small (CPU, int8), clip {duration:.1f} s")
    start = time.perf_counter()
    transcriber = load_transcriber("small")
    print(f"model load time: {time.perf_counter() - start:.1f} s")
    first = run(transcriber, None, "no_vocabulary")
    second = run(transcriber, VOCABULARY, "with_vocabulary")
    print(f"\nreal time factor: {first / duration:.2f}x without vocabulary, {second / duration:.2f}x with")


if __name__ == "__main__":
    main()
