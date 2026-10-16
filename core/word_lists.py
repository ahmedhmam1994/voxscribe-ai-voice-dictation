"""Export and import of the user's word lists (custom vocabulary and word
replacements) as one file, so they can be backed up, moved to another PC or
shared with the Android app, which reads the same format.

The file is JSON:

    {
      "format": "voxscribe-word-lists",
      "version": 1,
      "vocabulary": ["VoxScribe", "faster-whisper"],
      "replacements": [{"heard": "vox scribe", "replacement": "VoxScribe"}]
    }

A plain text file with one "heard => replacement" per line also imports, so
a list kept in a notes app or copied from the settings box works too.
"""

from __future__ import annotations

import json

from core.replacements import parse_replacements_text

FORMAT = "voxscribe-word-lists"
VERSION = 1
DEFAULT_FILE_NAME = "voxscribe-word-lists.json"


def export_text(vocabulary: list[str], pairs: list[tuple[str, str]]) -> str:
    data = {
        "format": FORMAT,
        "version": VERSION,
        "vocabulary": [term.strip() for term in vocabulary if term.strip()],
        "replacements": [
            {"heard": heard.strip(), "replacement": replacement.strip()}
            for heard, replacement in pairs
            if heard.strip()
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def parse_import(text: str) -> tuple[list[str], list[tuple[str, str]]]:
    """(vocabulary, replacements) read from an exported file or a plain text
    list. Raises ValueError when the file holds neither."""
    stripped = text.lstrip("﻿").strip()
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
        except ValueError as exc:
            raise ValueError("This file is not a VoxScribe word list.") from exc
        if not isinstance(data, dict) or data.get("format") != FORMAT:
            raise ValueError("This file is not a VoxScribe word list.")
        vocabulary = []
        for term in data.get("vocabulary") or []:
            # A term with a comma would split into two in the comma-separated box.
            if isinstance(term, str):
                vocabulary.extend(part.strip() for part in term.split(",") if part.strip())
        pairs = []
        for rule in data.get("replacements") or []:
            if not isinstance(rule, dict):
                continue
            heard, replacement = rule.get("heard"), rule.get("replacement", "")
            if isinstance(heard, str) and heard.strip() and isinstance(replacement, str):
                pairs.append((heard.strip(), replacement.strip()))
        return vocabulary, pairs
    pairs = parse_replacements_text(stripped)
    if not pairs:
        raise ValueError(
            'No word list found. Expected a VoxScribe export or "heard => replacement" lines.'
        )
    return [], pairs


def merge_replacements(
    existing: list[tuple[str, str]], incoming: list[tuple[str, str]]
) -> tuple[list[tuple[str, str]], int, int]:
    """(merged, added, changed). An incoming rule for the same heard words (any
    case) replaces the existing one in place, so two rules never fight; new
    rules go at the end in file order."""
    merged = list(existing)
    index_of = {heard.strip().lower(): i for i, (heard, _) in enumerate(merged)}
    added = changed = 0
    for heard, replacement in incoming:
        key = heard.strip().lower()
        if key in index_of:
            i = index_of[key]
            if merged[i] != (heard, replacement):
                if merged[i][1] != replacement:
                    changed += 1
                merged[i] = (heard, replacement)
        else:
            index_of[key] = len(merged)
            merged.append((heard, replacement))
            added += 1
    return merged, added, changed
