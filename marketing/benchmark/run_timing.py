"""Caption timing check on the labeled sample clip: card times against the speech.

Compares the old even split with the word timed split, measuring how far each
card start is from the moment the voice actually resumes after a pause.
"""

# ruff: noqa: E501
from __future__ import annotations

import sys
import time
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.captions import review_flags, split_segments, split_segments_timed  # noqa: E402
from core.srt import format_srt  # noqa: E402
from core.transcribe import load_transcriber  # noqa: E402

HERE = Path(__file__).resolve().parent
CLIP = HERE / "sample_episode.wav"
VOCAB = "Priya Raghunathan, Oluwaseun Adeyemi, Kubernetes, PostgreSQL"


def speech_resumes(path: Path, min_gap: float = 0.45) -> list[float]:
    with wave.open(str(path)) as wav:
        rate, n = wav.getframerate(), wav.getnframes()
        audio = np.frombuffer(wav.readframes(n), dtype=np.int16).astype(float)
    hop = int(rate * 0.02)
    energy = np.array([np.sqrt(np.mean(audio[i : i + hop] ** 2)) for i in range(0, len(audio) - hop, hop)])
    quiet = energy < max(energy.max() * 0.02, 30)
    resumes, i = [], 0
    while i < len(quiet):
        if quiet[i]:
            j = i
            while j < len(quiet) and quiet[j]:
                j += 1
            if (j - i) * 0.02 >= min_gap and j < len(quiet):
                resumes.append(j * 0.02)
            i = j
        else:
            i += 1
    return resumes


def report(label: str, cards, resumes) -> None:
    print(f"\n=== {label} ===")
    for start, end, text in cards:
        print(f"{start:6.2f}-{end:6.2f} ({end - start:4.1f}s)  {text.replace(chr(10), ' ')[:62]}")
    offsets = []
    for onset in resumes:
        near = min(cards, key=lambda c: abs(c[0] - onset))
        offsets.append(abs(near[0] - onset))
    print(f"card start vs voice resuming: worst {max(offsets):.2f}s, average {sum(offsets) / len(offsets):.2f}s")
    print(f"longest card on screen: {max(e - s for s, e, _ in cards):.1f}s")
    print(f"review flags: {review_flags(cards)}")


def main() -> None:
    transcriber = load_transcriber("small")
    start = time.perf_counter()
    plain = transcriber.transcribe_file_detailed(str(CLIP), initial_prompt=VOCAB, word_timestamps=False)
    t_plain = time.perf_counter() - start
    start = time.perf_counter()
    detailed = transcriber.transcribe_file_detailed(str(CLIP), initial_prompt=VOCAB, word_timestamps=True)
    t_words = time.perf_counter() - start
    print(f"processing: {t_plain:.1f}s without word timestamps, {t_words:.1f}s with them")
    resumes = speech_resumes(CLIP)
    print("voice resumes after a pause at:", [round(r, 2) for r in resumes])
    segments = [(s, e, t) for s, e, t, _w in plain]
    report("even split (before)", split_segments(segments, 42), resumes)
    timed = split_segments_timed(detailed, 42)
    report("word timed (now)", timed, resumes)
    (HERE / "sample_episode_word_timed.srt").write_text(format_srt(timed), encoding="utf-8")


if __name__ == "__main__":
    main()
