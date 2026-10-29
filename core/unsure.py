"""Unsure-word marks: after a dictation, the transcript on the Dictation page
underlines the words the speech model was least sure about, so you check those
instead of rereading everything. Whisper and Parakeet report how sure they were;
Cohere and Moonshine do not, so nothing is marked with them. The text typed into other
apps is never changed: only VoxScribe's own transcript shows the marks.

Off by default (Settings, Text), because asking Whisper for word-level
confidence makes each dictation a little slower.
"""

from __future__ import annotations

import html
import math
import re

# A word Whisper gave less than this probability is worth a second look.
UNSURE_BELOW = 0.6
# Parakeet's word score (the geometric mean over the pieces of the word) runs higher.
# On recorded clips, words below 0.8 were almost always wrong ones.
SHERPA_UNSURE_BELOW = 0.8
_MIN_LENGTH = 3
# Small words Whisper is often unsure about for no reason that helps the reader.
_FILLER = frozenset(
    "and are but can for from had has have her him his its not our she that the them then "
    "they this was were what when who will with you your".split()
)
_TOKEN = re.compile(r"[\w'’-]+|[^\w'’-]+")
_EDGE = " \t\n.,;:!?\"'()[]{}“”‘’"


def clean_word(word: str) -> str:
    return word.strip(_EDGE).lower()


def words_with_confidence(
    tokens: list[str], log_probs: list[float]
) -> list[tuple[str, float]]:
    """Joins sub-word tokens into words with one score each: the geometric mean of
    the probabilities of the pieces. A token that starts with a space (or the
    sentencepiece mark) starts a new word. Empty when the two lists do not line up."""
    if not tokens or len(tokens) != len(log_probs):
        return []
    words: list[tuple[str, list[float]]] = []
    for token, log_prob in zip(tokens, log_probs):
        if token.startswith((" ", "▁")) or not words:
            words.append((token.lstrip(" ▁"), [log_prob]))
        else:
            words[-1] = (words[-1][0] + token, [*words[-1][1], log_prob])
    return [
        (word, math.exp(sum(logs) / len(logs))) for word, logs in words if word.strip()
    ]


def unsure_words(
    words: list[tuple[str, float]], below: float = UNSURE_BELOW
) -> list[str]:
    """The distinct unsure words (lowercase, no punctuation), longest first so a
    caller that matches in order meets the specific word before a short one."""
    found = {
        clean_word(word)
        for word, probability in words
        if probability < below
        and len(clean_word(word)) >= _MIN_LENGTH
        and clean_word(word) not in _FILLER
    }
    return sorted(found, key=lambda w: (-len(w), w))


def mark_html(text: str, unsure: list[str], color: str) -> str | None:
    """`text` as HTML with each unsure word underlined in `color`, or None when
    no word of the text is marked (the caller then shows the plain text)."""
    if not unsure:
        return None
    wanted = set(unsure)
    pieces: list[str] = []
    marked = 0
    for token in _TOKEN.findall(text):
        if clean_word(token) in wanted and clean_word(token):
            pieces.append(
                f'<span style="color:{color}; text-decoration: underline;">'
                f"{html.escape(token)}</span>"
            )
            marked += 1
        else:
            pieces.append(html.escape(token))
    if not marked:
        return None
    return "".join(pieces).replace("\n", "<br>")
