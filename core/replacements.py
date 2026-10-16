"""Custom word replacements: a free-tier find-and-replace list applied to
every transcription, for fixing words Whisper keeps getting wrong the same
way (e.g. "vox scribe" -> "VoxScribe"). Different from Pro snippets, which
swap a whole utterance for a block of text; this edits words inside a
sentence.

Stored as JSON for the same reason snippets are: a replacement can contain
commas, so comma-splitting would corrupt it.
"""

from __future__ import annotations

import json
import re

from PySide6.QtCore import QSettings


def _settings() -> QSettings:
    return QSettings("VoxScribe", "VoxScribe")


def get_replacements() -> list[tuple[str, str]]:
    raw = _settings().value("replacements", "")
    if not raw:
        return []
    try:
        pairs = json.loads(raw)
    except ValueError:
        return []
    return [(str(a), str(b)) for a, b in pairs if isinstance(a, str) and isinstance(b, str)]


def set_replacements(pairs: list[tuple[str, str]]) -> None:
    cleaned = [(a.strip(), b.strip()) for a, b in pairs if a.strip()]
    _settings().setValue("replacements", json.dumps(cleaned))


def parse_replacements_text(text: str) -> list[tuple[str, str]]:
    """One "heard => replacement" pair per line. Lines without "=>" or with
    an empty left side are skipped. An empty right side is allowed and
    deletes the word."""
    pairs = []
    for line in text.splitlines():
        if "=>" not in line:
            continue
        heard, replacement = line.split("=>", 1)
        if heard.strip():
            pairs.append((heard.strip(), replacement.strip()))
    return pairs


def apply_replacements(text: str, pairs: list[tuple[str, str]] | None = None) -> str:
    """Case-insensitive, whole-word replacement, applied in list order."""
    if not text:
        return text
    if pairs is None:
        pairs = get_replacements()
    for heard, replacement in pairs:
        pattern = re.compile(r"(?<!\w)" + re.escape(heard) + r"(?!\w)", re.IGNORECASE)
        text = pattern.sub(lambda _m, r=replacement: r, text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    return text.strip()


def clean_selection(text: str) -> str:
    """The words picked from a transcript, without the punctuation and spaces
    around them. "whisker," becomes "whisker"; apostrophes and hyphens inside
    a word stay."""
    collapsed = re.sub(r"\s+", " ", text.strip())
    return re.sub(r"^\W+|\W+$", "", collapsed)


def add_rule(
    pairs: list[tuple[str, str]], heard: str, replacement: str
) -> tuple[list[tuple[str, str]], str]:
    """Add "heard => replacement" to `pairs`. Returns (new_pairs, status) where
    status is "added", "updated" (a rule for the same words in any case was
    changed in place, so two rules never fight), "unchanged" (the same rule was
    already there) or "invalid" (nothing to fix, or it already reads that way)."""
    heard = clean_selection(heard)
    replacement = re.sub(r"\s*\n\s*", " ", replacement.strip())
    if not heard or not replacement or heard == replacement:
        return pairs, "invalid"
    for index, (old, new) in enumerate(pairs):
        if old.strip().lower() == heard.lower():
            if new.strip() == replacement:
                return pairs, "unchanged"
            updated = list(pairs)
            updated[index] = (heard, replacement)
            return updated, "updated"
    return [*pairs, (heard, replacement)], "added"


def add_replacement(heard: str, replacement: str) -> str:
    """Save one correction made from the transcript box. Returns the status
    from add_rule; only "added" and "updated" change what is stored."""
    pairs, status = add_rule(get_replacements(), heard, replacement)
    if status in ("added", "updated"):
        set_replacements(pairs)
    return status
