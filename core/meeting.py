"""Turns the two meeting recordings (core/meeting_recorder.py) into one
conversation: "You" from the microphone, "Others" from what the PC played.

Each track is transcribed on its own, then the lines are merged by time. Two
things need care:

* Echo. With speakers instead of headphones the microphone also hears the other
  people, a little quieter and garbled. A microphone line whose words are mostly
  found in an "Others" line said at the same moment (even a fragment of it), or
  that is much quieter than the sound playing then, is dropped.
* Short pauses. Lines by the same speaker with only a short gap between them are
  joined, so the note reads as speech, not as one line per breath.

Pure logic apart from reading the WAV files, so it is easy to test.
"""

from __future__ import annotations

import difflib
import re
import wave
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

YOU = "You"
OTHERS = "Others"
ECHO_COVERAGE = 0.6
ECHO_QUIET_RATIO = 0.4
ECHO_QUIET_FLOOR = 0.03
JOIN_GAP_SECONDS = 2.0
_WORD = re.compile(r"[\w']+")

Segment = tuple[float, float, str]  # start, end, text


@dataclass
class Line:
    start: float
    end: float
    speaker: str
    text: str


def wav_rms(path: Path, start: float, end: float) -> float:
    """Loudness (RMS, 0 to 1) of one stretch of a 16-bit mono WAV file."""
    try:
        with wave.open(str(path)) as wav:
            rate = wav.getframerate()
            wav.setpos(max(0, min(wav.getnframes(), int(start * rate))))
            frames = wav.readframes(max(0, int((end - start) * rate)))
    except (OSError, wave.Error, EOFError):
        return 0.0
    samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768
    return float(np.sqrt(np.mean(samples**2))) if len(samples) else 0.0


def _words(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text)]


def _overlap(a: Segment, b: Segment) -> float:
    """Seconds the two segments share."""
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


def _is_echo(
    mine: Segment,
    others: list[Segment],
    you_rms: Callable[[float, float], float] | None,
    others_rms: Callable[[float, float], float] | None,
) -> bool:
    length = max(mine[1] - mine[0], 0.01)
    overlapping = [o for o in others if _overlap(mine, o) / length >= 0.3]
    if not overlapping:
        return False
    mine_words = _words(mine[2])
    for other in overlapping:
        other_words = _words(other[2])
        if mine_words and other_words:
            blocks = difflib.SequenceMatcher(None, mine_words, other_words).get_matching_blocks()
            if sum(block.size for block in blocks) / len(mine_words) >= ECHO_COVERAGE:
                return True
    if you_rms is not None and others_rms is not None:
        quiet = you_rms(mine[0], mine[1])
        loud = others_rms(mine[0], mine[1])
        if quiet < ECHO_QUIET_FLOOR and quiet < ECHO_QUIET_RATIO * loud:
            return True
    return False


def merge_tracks(
    you: list[Segment],
    others: list[Segment],
    you_rms: Callable[[float, float], float] | None = None,
    others_rms: Callable[[float, float], float] | None = None,
) -> list[Line]:
    """One conversation in time order, with echo removed and neighbouring lines
    of the same speaker joined."""
    lines = [
        Line(start, end, YOU, text.strip())
        for start, end, text in you
        if text.strip() and not _is_echo((start, end, text), others, you_rms, others_rms)
    ]
    lines += [Line(start, end, OTHERS, text.strip()) for start, end, text in others if text.strip()]
    lines.sort(key=lambda line: (line.start, line.speaker))
    merged: list[Line] = []
    for line in lines:
        last = merged[-1] if merged else None
        if last and last.speaker == line.speaker and line.start - last.end <= JOIN_GAP_SECONDS:
            last.end = max(last.end, line.end)
            last.text = f"{last.text} {line.text}"
        else:
            merged.append(Line(line.start, line.end, line.speaker, line.text))
    return merged


def transcribe_meeting(
    transcriber,  # noqa: ANN001 -- a Transcriber or SpeechRouter
    mic_path: Path,
    others_path: Path | None,
    language: str | None,
    prompt: str | None = None,
    postprocess: Callable[[str], str] | None = None,
    on_progress: Callable[[float], None] | None = None,
) -> list[Line]:
    """Transcribes both tracks with Whisper (the model that gives timestamps) and
    merges them. `on_progress` gets 0.0 to 1.0 across both tracks."""
    tracks = [(mic_path, "you")] + ([(others_path, "others")] if others_path else [])
    done: dict[str, list[Segment]] = {}
    for index, (path, name) in enumerate(tracks):
        share = 1 / len(tracks)

        def report(percent: float, base: float = index * share, span: float = share) -> None:
            if on_progress is not None:
                on_progress(min(1.0, base + span * percent / 100))

        done[name] = transcriber.transcribe_file_segments(
            str(path), language=language, initial_prompt=prompt, on_progress=report
        )
    lines = merge_tracks(
        done.get("you", []),
        done.get("others", []),
        lambda a, b: wav_rms(mic_path, a, b),
        (lambda a, b: wav_rms(others_path, a, b)) if others_path else None,
    )
    if postprocess is not None:
        for line in lines:
            line.text = postprocess(line.text)
    if on_progress is not None:
        on_progress(1.0)
    return lines
