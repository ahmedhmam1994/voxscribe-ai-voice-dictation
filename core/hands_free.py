"""Hands-free mode: talk without holding a key, and each phrase is typed when you pause.

This module is the part that needs no mic or model, so it can be tested:
`Segmenter` cuts a stream of 16 kHz audio into phrases at pauses, and the text
checks decide what happens to a transcribed phrase (dropped as a Whisper phantom
line, or the spoken "stop listening").

Settings come from the Phase 0 measurements on a real Bluetooth headset
(benchmark/handsfree): a detector threshold of 0.5 with auto gain typed nothing on
keyboard, mouse, room and cough noise, where the older 0.1 setting typed
"Thank you." from typing. A 1.2 s pause before cutting kept the delay down without
losing more words than a longer one.
"""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Callable

import numpy as np

SAMPLE_RATE = 16_000
FRAME_SIZE = 512  # one detector frame, 32 ms
FRAME_SEC = FRAME_SIZE / SAMPLE_RATE

VAD_THRESHOLD = 0.5
# Silence after speech before the phrase is cut and typed.
PAUSE_SEC = 1.2
# Speech must last this long before a phrase starts, so a click can't start one.
START_FRAMES = 4
# Phrases shorter than this are dropped as noise.
MIN_PHRASE_SEC = 0.3
# A phrase is cut here even without a pause, so a long run never waits minutes
# to be typed and never gets too long for the model.
MAX_PHRASE_SEC = 25.0
# Audio kept from just before speech starts, so the first word is not lost.
# 0.3 s lost soft starts on the headset ("Let's meet" came out "It", "Hi Sarah"
# came out "Hi sorrow"); 0.6 s kept them.
LEAD_IN_SEC = 0.6
# A session ends by itself after this long with no speech.
IDLE_STOP_SEC = 120.0
# The text typed so far that is handed to the model as context for the next
# phrase (it cut word errors on the Phase 0 clips from 10.5% to 8.9%).
CONTEXT_CHARS = 200


class Segmenter:
    """Cuts 16 kHz audio frames into phrases at pauses.

    `push(frame)` takes one FRAME_SIZE frame and returns a list of events:
    ("start",) when speech begins, ("phrase", audio, speech_sec) when a phrase is
    finished, and ("idle",) once after IDLE_STOP_SEC with no speech.
    """

    def __init__(
        self,
        is_speech: Callable[[np.ndarray], bool],
        pause_sec: float = PAUSE_SEC,
        start_frames: int = START_FRAMES,
        min_phrase_sec: float = MIN_PHRASE_SEC,
        max_phrase_sec: float = MAX_PHRASE_SEC,
        lead_in_sec: float = LEAD_IN_SEC,
        idle_stop_sec: float = IDLE_STOP_SEC,
    ):
        self._is_speech = is_speech
        self._pause_frames = max(1, round(pause_sec / FRAME_SEC))
        self._start_frames = max(1, start_frames)
        self._min_frames = max(1, round(min_phrase_sec / FRAME_SEC))
        self._max_frames = max(self._pause_frames + 1, round(max_phrase_sec / FRAME_SEC))
        self._idle_frames = max(1, round(idle_stop_sec / FRAME_SEC))
        self._lead_in: deque[np.ndarray] = deque(maxlen=max(0, round(lead_in_sec / FRAME_SEC)))
        self._pending: list[np.ndarray] = []
        self._phrase: list[np.ndarray] = []
        self._speech_frames = 0
        self._silence_run = 0
        self._quiet_frames = 0
        self._idle_sent = False
        self.in_phrase = False

    def push(self, frame: np.ndarray) -> list[tuple]:
        speech = self._is_speech(frame)
        if self.in_phrase:
            self._phrase.append(frame)
            if speech:
                self._speech_frames += 1
                self._silence_run = 0
            else:
                self._silence_run += 1
            if self._silence_run >= self._pause_frames or len(self._phrase) >= self._max_frames:
                return self._finish()
            return []

        if speech:
            self._pending.append(frame)
            if len(self._pending) >= self._start_frames:
                self.in_phrase = True
                self._phrase = [*self._lead_in, *self._pending]
                self._speech_frames = len(self._pending)
                self._silence_run = 0
                self._pending = []
                self._lead_in.clear()
                self._quiet_frames = 0
                self._idle_sent = False
                return [("start",)]
            return []

        # A short run of speech that did not last becomes lead-in for the next one.
        self._lead_in.extend(self._pending)
        self._pending = []
        self._lead_in.append(frame)
        self._quiet_frames += 1
        if self._quiet_frames >= self._idle_frames and not self._idle_sent:
            self._idle_sent = True
            return [("idle",)]
        return []

    def flush(self) -> list[tuple]:
        """Finishes a phrase still being spoken (the session is ending)."""
        return self._finish() if self.in_phrase else []

    def _finish(self) -> list[tuple]:
        # Trailing silence past a short tail is not needed by the model.
        keep = len(self._phrase) - max(0, self._silence_run - round(0.3 / FRAME_SEC))
        frames = self._phrase[:keep]
        speech_frames = self._speech_frames
        self._phrase = []
        self._speech_frames = 0
        self._silence_run = 0
        self._quiet_frames = 0
        self.in_phrase = False
        if speech_frames < self._min_frames:
            return []
        audio = np.concatenate(frames).astype(np.float32)
        return [("phrase", audio, speech_frames * FRAME_SEC)]


class Resampler:
    """Turns mic chunks at the device's own rate into 16 kHz detector frames."""

    def __init__(self, source_rate: int):
        self.source_rate = int(source_rate)
        self._raw = np.zeros(0, dtype=np.float32)
        self._out = np.zeros(0, dtype=np.float32)

    def frames(self, chunk: np.ndarray) -> list[np.ndarray]:
        self._raw = np.concatenate([self._raw, chunk.astype(np.float32)])
        rate = self.source_rate
        if rate == SAMPLE_RATE:
            converted, self._raw = self._raw, np.zeros(0, dtype=np.float32)
        elif rate % SAMPLE_RATE == 0:
            # 32, 48 kHz...: average each group of samples, which also keeps
            # sound above 8 kHz from folding back into the speech band.
            step = rate // SAMPLE_RATE
            usable = len(self._raw) // step * step
            converted = self._raw[:usable].reshape(-1, step).mean(axis=1)
            self._raw = self._raw[usable:]
        else:
            # 44.1 kHz and other odd rates: straight-line steps between samples.
            n = int(len(self._raw) * SAMPLE_RATE / rate)
            if n == 0:
                return []
            used = int(n * rate / SAMPLE_RATE)
            src = np.arange(used)
            dst = np.arange(n) * (rate / SAMPLE_RATE)
            converted = np.interp(dst, src, self._raw[:used])
            self._raw = self._raw[used:]
        self._out = np.concatenate([self._out, converted.astype(np.float32)])
        count = len(self._out) // FRAME_SIZE
        out = [self._out[i * FRAME_SIZE : (i + 1) * FRAME_SIZE] for i in range(count)]
        self._out = self._out[count * FRAME_SIZE :]
        return out


def _words(text: str) -> list[str]:
    return re.sub(r"[^a-z0-9' ]+", " ", text.lower()).split()


# Lines Whisper writes when it hears noise or breathing, learned from video
# subtitles. Nobody dictates them on their own, so a phrase that is only one of
# these is dropped. "Thank you" is not here: people do dictate it.
_PHANTOM_LINES = {
    "thanks for watching",
    "thank you for watching",
    "thanks for watching bye",
    "thank you for watching bye",
    "thank you so much for watching",
    "please subscribe",
    "subscribe to my channel",
    "like and subscribe",
    "see you in the next video",
    "see you next time",
    "subtitles by the amara org community",
    "you",
}


def is_phantom(text: str) -> bool:
    """True for a phrase that is only a known Whisper phantom line or a hum."""
    words = _words(text)
    if not words:
        return True
    line = " ".join(words)
    if line in _PHANTOM_LINES:
        return True
    if all(w in ("bye", "hmm", "hm", "mm", "mmm", "uh", "um") for w in words):
        return True
    # "MMMMMMMMMM", "hmmmmm": one sound held, not a word.
    return len(words) == 1 and re.fullmatch(r"h?m{3,}|a{3,}|o{3,}", line) is not None


def is_stop_command(text: str) -> bool:
    """True for "stop listening" said on its own. The model often loses or
    changes the first word of such a short phrase ("Listening.", "Tub listening"),
    so any phrase of up to three words that ends in "listening" counts."""
    words = _words(text)
    return 0 < len(words) <= 3 and words[-1] == "listening"


# Spoken commands a hands-free phrase is matched against when it is said on its
# own. Whisper mishears such short phrases on a headset ("New line" came out
# "New online", "Scratch that" came out "ScratchZ"), so a close match counts.
COMMAND_PHRASES = (
    "new line", "new paragraph",
    "scratch that", "undo that", "delete that", "delete last word", "delete last sentence",
    "send it", "press enter",
    "period", "full stop", "comma", "question mark",
    "capitalize that", "all caps",
    "make it shorter", "make it formal", "make it friendly", "bullet points", "fix that",
)  # fmt: skip
# Only phrases this short are compared, so a sentence is never taken for a command.
COMMAND_MAX_WORDS = 4
COMMAND_MAX_SPEECH_SEC = 2.0
COMMAND_MIN_SIMILARITY = 0.72


# Not matched loosely: they delete text, and "Not that." is close to "undo that".
# They still work when heard right, through the normal command path.
_EXACT_ONLY = {"undo that", "delete that", "delete last word", "delete last sentence"}


def match_command(text: str) -> str | None:
    """The command a short, misheard phrase was meant to be ("New online." is
    "new line"), or None when it is not close to any command."""
    from difflib import SequenceMatcher

    words = _words(text)
    if not words or len(words) > COMMAND_MAX_WORDS:
        return None
    heard = "".join(words)
    best, best_score = None, 0.0
    for phrase in COMMAND_PHRASES:
        if phrase in _EXACT_ONLY and " ".join(words) != phrase:
            continue
        score = SequenceMatcher(None, heard, phrase.replace(" ", "")).ratio()
        if score > best_score:
            best, best_score = phrase, score
    if best is None or best_score < COMMAND_MIN_SIMILARITY:
        return None
    # "Make it so." is close to "make it shorter" as a whole but ends on a
    # different word; a real mishearing keeps the last word's sound.
    last = best.split()[-1]
    if len(words) > 1 and len(best.split()) > 1:
        if SequenceMatcher(None, words[-1], last).ratio() < 0.5:
            return None
    return best


# A phrase cut at a pause that ends like this was most likely cut mid-sentence
# ("I think we should..."): it is held and decoded again together with what
# comes next, since one piece is decoded far better than two halves.
HOLD_SEC = 3.0
_OPEN_ENDINGS = {
    "and", "or", "but", "so", "because", "if", "then", "to", "the", "a", "an", "of",
    "for", "with", "which", "is", "was", "are", "were", "we", "i", "he", "she",
    "they", "at", "by", "from", "my", "your", "our", "their", "should", "will",
    "would", "can", "could", "into",
}  # fmt: skip


def looks_unfinished(text: str) -> bool:
    """True when a phrase seems to stop mid-sentence: it trails off ("..."),
    ends on a comma, has no closing punctuation or ends on a word like "and"."""
    stripped = text.strip()
    words = _words(stripped)
    if not words:
        return False
    if stripped.endswith(("...", "…", ",", ":", ";", "-")):
        return True
    if stripped[-1] not in ".?!":
        return True
    # "you", "it" and "that" are left out: "Thank you." and "Send it." are whole.
    return stripped[-1] == "." and words[-1] in _OPEN_ENDINGS


# "change Tuesday to Friday": swaps words in what this session typed. The part
# being changed is kept short, so "change the plan to something cheaper and
# simpler for the team" stays a sentence unless it really names typed words.
# The first word is often misheard ("Fange Tuesday to Friday."), so it only
# has to sound like "change"; the caller still checks the words were typed.
_CHANGE_RE = re.compile(r"^([a-z']+)\s+(.+?)\s+to\s+(.+?)[.!?]*$", re.IGNORECASE)
CHANGE_MAX_WORDS = 4
CHANGE_MAX_SPEECH_SEC = 3.5


def change_command(text: str) -> tuple[str, str] | None:
    """("Tuesday", "Friday") for "Change Tuesday to Friday.", else None."""
    from difflib import SequenceMatcher

    match = _CHANGE_RE.match(text.strip())
    if not match:
        return None
    verb = match.group(1).lower()
    if verb != "change" and SequenceMatcher(None, verb, "change").ratio() < 0.6:
        return None
    old, new = match.group(2).strip(" ,"), match.group(3).strip(" ,")
    if not old or not new or len(old.split()) > CHANGE_MAX_WORDS:
        return None
    return old, new


class Block:
    """What a hands-free session typed into one box since the last line break,
    as (space typed before it, phrase) pieces, so "make that shorter" and
    "change X to Y" act on all of it and "scratch that" removes the last
    phrase with its space."""

    def __init__(self) -> None:
        self.pieces: list[tuple[str, str]] = []
        self.hwnd: int | None = None

    def clear(self) -> None:
        self.pieces = []
        self.hwnd = None

    def add(self, lead: str, text: str, hwnd: int | None, continues: bool) -> None:
        if continues and self.pieces and hwnd == self.hwnd:
            self.pieces.append((lead, text))
        else:
            self.pieces = [("", text)]
            self.hwnd = hwnd

    @property
    def text(self) -> str:
        if not self.pieces:
            return ""
        return self.pieces[0][1] + "".join(lead + t for lead, t in self.pieces[1:])

    def replaced(self, old: str, new: str) -> None:
        """After `old` on screen was rewritten to `new`."""
        if not self.pieces:
            return
        if old == self.text:
            self.pieces = [("", new)] if new else []
        elif old == self.pieces[-1][1]:
            self.pieces[-1] = (self.pieces[-1][0], new)
        else:
            self.clear()

    def pop(self) -> tuple[str, str] | None:
        return self.pieces.pop() if self.pieces else None


# Whisper is given the end of what was typed as its prompt (context_prompt),
# and on a short phrase it sometimes writes that end out again before the new
# words: "Change Tuesday to Friday." came back as "Me on Tuesday at noon to go
# over the last two bugs. Change Tuesday to Friday." Nothing is cut out by
# guesswork (the user may really have said those words): such a phrase is only
# decoded once more without the typed text in the prompt.
ECHO_MIN_WORDS = 4


def repeats_typed_end(text: str, typed: list[str]) -> bool:
    """True when `text` starts with the last ECHO_MIN_WORDS or more words of what
    was typed (its first word may be clipped: "Me" for "meet")."""
    tail = _words(" ".join(typed))[-60:]
    heard = _words(text)
    if len(tail) < ECHO_MIN_WORDS or len(heard) < ECHO_MIN_WORDS:
        return False
    for skip in (0, 1):
        rest = heard[skip:]
        for k in range(min(len(rest), len(tail)), ECHO_MIN_WORDS - 1, -1):
            if rest[:k] != tail[-k:]:
                continue
            if not skip:
                return True
            before = tail[-k - 1] if len(tail) > k else ""
            if before and heard[0] in before:
                return True
            break
    return False


def context_prompt(vocabulary: str | None, typed: list[str]) -> str | None:
    """The model's prompt for the next phrase: the user's words, then the end of
    what this session typed so far."""
    recent = " ".join(typed)[-CONTEXT_CHARS:].lstrip()
    parts = [p for p in (vocabulary, recent) if p]
    return " ".join(parts) or None
