"""Fast speech with no pauses: how far are Whisper's word times, and the caption
cards built from them, from the moment each word is actually spoken?

The reference word times come from the speech engine that produced the clip
(sample_fast_words.tsv: seconds and word, one per line). That engine's event
clock runs slow against the audio it writes (its last word lands near 17 s in a
13 s file), so the reference is rescaled once so that its first and last word
span the audible speech measured from the audio itself. Whisper's times are not
used for that, but the figures are still an estimate, not an exact measurement.

Run from the repo root:  venv\\Scripts\\python.exe marketing\\benchmark\\run_fast_speech.py
"""

# ruff: noqa: E501
from __future__ import annotations

import re
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.captions import review_flags, split_segments, split_segments_timed  # noqa: E402
from core.transcribe import load_transcriber  # noqa: E402

HERE = Path(__file__).resolve().parent
CLIP = HERE / "sample_fast.wav"
LAST_WORD_SECONDS = 0.45


def norm(word: str) -> str:
    return re.sub(r"[^a-z0-9']", "", word.lower())


def audible_span(path: Path) -> tuple[float, float]:
    """When the speech starts and stops, from the audio energy."""
    with wave.open(str(path)) as wav:
        rate = wav.getframerate()
        audio = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16).astype(float)
    hop = int(rate * 0.02)
    energy = np.array([np.sqrt(np.mean(audio[i : i + hop] ** 2)) for i in range(0, len(audio) - hop, hop)])
    active = np.where(energy > energy.max() * 0.05)[0]
    return active[0] * 0.02, (active[-1] + 1) * 0.02


def load_reference(first_on: float, last_off: float) -> list[tuple[float, str]]:
    rows = []
    for line in (HERE / "sample_fast_words.tsv").read_text(encoding="utf-8-sig").splitlines():
        seconds, _, word = line.partition("\t")
        if word.strip():
            rows.append((float(seconds), norm(word)))
    scale = (last_off - LAST_WORD_SECONDS - first_on) / (rows[-1][0] - rows[0][0])
    print(f"audible speech {first_on:.2f}-{last_off:.2f}s, reference clock scale {scale:.3f}")
    return [(first_on + (t - rows[0][0]) * scale, w) for t, w in rows]


def main() -> None:
    first_on, last_off = audible_span(CLIP)
    reference = load_reference(first_on, last_off)
    detailed = load_transcriber("small").transcribe_file_detailed(str(CLIP), word_timestamps=True)
    heard = [(s, norm(w)) for _a, _b, _t, words in detailed for s, _e, w in words]
    errors = sorted(abs(h[0] - r[0]) for h, r in zip(heard, reference, strict=False) if h[1] == r[1])
    print(f"matched {len(errors)} of {len(reference)} words")
    print(
        f"word start error: median {errors[len(errors) // 2]:.2f}s, "
        f"90th percentile {errors[int(len(errors) * 0.9)]:.2f}s, worst {errors[-1]:.2f}s"
    )

    def card_error(cards) -> tuple[float, float]:
        diffs = []
        for start, _end, text in cards:
            near = [t for t, w in reference if w == norm(text.split()[0])]
            if near:
                diffs.append(min(abs(start - t) for t in near))
        return sum(diffs) / len(diffs), max(diffs)

    timed = split_segments_timed(detailed, 42)
    even = split_segments([(s, e, t) for s, e, t, _w in detailed], 42)
    for label, cards in (("even split", even), ("word timed", timed)):
        average, worst = card_error(cards)
        longest = max(e - s for s, e, _ in cards)
        print(
            f"{label}: {len(cards)} cards, card start vs voice average {average:.2f}s, "
            f"worst {worst:.2f}s, longest card {longest:.1f}s, review flags {len(review_flags(cards))}"
        )


if __name__ == "__main__":
    main()
