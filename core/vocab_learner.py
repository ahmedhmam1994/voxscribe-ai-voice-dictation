"""Learn a custom vocabulary from the user's own files -- a Pro feature (see
core/license.py). Reads text files in a folder, picks out the names, acronyms
and identifiers that Whisper tends to mishear, and returns them for the
existing custom vocabulary (core/settings.py).

Everything happens on this PC: the files are read here and nothing is sent
anywhere. No dictionary or model is used, only the shape of a word:
  * CamelCase and snake_case identifiers
  * ACRONYMS
  * words with digits inside ("Whisper3")
  * Capitalized words that appear mid-sentence (names, products)
A term has to appear at least twice, so a one-off typo is not learned.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

TEXT_SUFFIXES = {
    ".txt", ".md", ".rst", ".csv", ".json", ".py", ".js", ".ts", ".tsx", ".jsx",
    ".java", ".kt", ".cs", ".go", ".rs", ".html", ".css", ".yaml", ".yml", ".toml",
}
MAX_FILES = 300
MAX_BYTES_PER_FILE = 400_000
MAX_TERMS = 60
MIN_COUNT = 2

_SKIP_DIRS = {".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build"}
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{2,}")
_CAMEL_RE = re.compile(r"^[a-z]+(?:[A-Z][a-z0-9]+)+$|^(?:[A-Z][a-z0-9]+){2,}$")
_ACRONYM_RE = re.compile(r"^[A-Z]{2,6}[0-9]*$")
_DIGIT_RE = re.compile(r"^[A-Za-z]+[0-9]+[A-Za-z0-9]*$")

# Capitalized words that are just ordinary sentence furniture.
_COMMON_CAPITALIZED = {
    "The", "This", "That", "These", "Those", "There", "Then", "They", "Their", "When",
    "What", "Where", "Which", "While", "With", "Without", "Will", "Would", "Should",
    "Could", "Can", "And", "But", "For", "Not", "You", "Your", "Our", "We", "It", "Its",
    "If", "In", "On", "At", "As", "Is", "Are", "Was", "Were", "Be", "To", "Of", "By",
    "From", "Also", "Note", "Todo", "True", "False", "None", "Null", "Yes", "No",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December",
}
_COMMON_ACRONYMS = {"THE", "AND", "NOT", "FOR", "TODO", "FIXME", "NOTE", "TRUE", "FALSE"}


def _is_sentence_start(text: str, index: int) -> bool:
    before = text[:index].rstrip(" \t\"'(*-#>")
    return not before or before[-1] in ".!?\n:"


def extract_terms(text: str) -> Counter[str]:
    """Counts the vocabulary-worthy terms in one piece of text."""
    counts: Counter[str] = Counter()
    for match in _WORD_RE.finditer(text):
        word = match.group(0)
        if _CAMEL_RE.match(word) or "_" in word.strip("_") and word.lower() == word:
            counts[word] += 1
        elif _ACRONYM_RE.match(word) and word not in _COMMON_ACRONYMS:
            counts[word] += 1
        elif _DIGIT_RE.match(word):
            counts[word] += 1
        elif (
            word[0].isupper()
            and word not in _COMMON_CAPITALIZED
            and not _is_sentence_start(text, match.start())
        ):
            counts[word] += 1
    return counts


def _text_files(folder: Path) -> list[Path]:
    files: list[Path] = []
    for path in folder.rglob("*"):
        if len(files) >= MAX_FILES:
            break
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            files.append(path)
    return files


def learn_from_folder(folder: str | Path, limit: int = MAX_TERMS) -> list[str]:
    """The most common vocabulary-worthy terms in the text files under `folder`."""
    root = Path(folder)
    if not root.is_dir():
        return []
    total: Counter[str] = Counter()
    for path in _text_files(root):
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as handle:
                total.update(extract_terms(handle.read(MAX_BYTES_PER_FILE)))
        except OSError:
            continue
    return [term for term, count in total.most_common(limit) if count >= MIN_COUNT]


def merge_vocabulary(existing: list[str], learned: list[str]) -> list[str]:
    """Existing terms first, then newly learned ones, without repeats (any case)."""
    seen = {term.lower() for term in existing}
    merged = list(existing)
    for term in learned:
        if term.lower() not in seen:
            seen.add(term.lower())
            merged.append(term)
    return merged
