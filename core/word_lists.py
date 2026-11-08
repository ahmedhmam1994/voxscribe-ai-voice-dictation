"""Export and import of the user's words and text tools as one file, so they
can be backed up, moved to another PC or shared with the Android app, which
reads and writes the same format.

The file is JSON:

    {
      "format": "voxscribe-word-lists",
      "version": 2,
      "vocabulary": ["VoxScribe", "faster-whisper"],
      "replacements": [{"heard": "vox scribe", "replacement": "VoxScribe"}],
      "learned": [{"heard": "shivon", "fixed": "Siobhan"}],
      "snippets": [{"trigger": "my sig", "expansion": "Best,\\nSam"}],
      "templates": [{"name": "bug report", "body": "Title: {title}"}],
      "profile": {"field": "medical", "app": "email"}
    }

Version 1 files have only "vocabulary" and "replacements"; every later key is
optional, and a reader skips keys it does not know, so an older app still
imports the word lists from a newer file. A plain text file with one
"heard => replacement" per line also imports, so a list kept in a notes app
or copied from the settings box works too.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field

from core.replacements import parse_replacements_text

FORMAT = "voxscribe-word-lists"
VERSION = 2
DEFAULT_FILE_NAME = "voxscribe-word-lists.json"

Pair = tuple[str, str]


@dataclass
class Bundle:
    """Everything one file can carry. Empty lists mean "not in the file"."""

    vocabulary: list[str] = field(default_factory=list)
    replacements: list[Pair] = field(default_factory=list)
    learned: list[Pair] = field(default_factory=list)  # (heard, fixed)
    snippets: list[Pair] = field(default_factory=list)  # (trigger, expansion)
    templates: list[Pair] = field(default_factory=list)  # (name, body)
    profile: dict[str, str] = field(default_factory=dict)  # "field", "app"

    def counts(self) -> dict[str, int]:
        return {
            "vocabulary": len(self.vocabulary),
            "replacements": len(self.replacements),
            "learned": len(self.learned),
            "snippets": len(self.snippets),
            "templates": len(self.templates),
        }


def _pairs(items: Iterable[Pair], first: str, second: str, keep_empty: bool) -> list[dict]:
    return [
        {first: a.strip(), second: b if second in ("expansion", "body") else b.strip()}
        for a, b in items
        if a.strip() and (keep_empty or b.strip())
    ]


def export_bundle(bundle: Bundle) -> str:
    data: dict = {
        "format": FORMAT,
        "version": VERSION,
        "vocabulary": [term.strip() for term in bundle.vocabulary if term.strip()],
        "replacements": _pairs(bundle.replacements, "heard", "replacement", keep_empty=True),
        "learned": _pairs(bundle.learned, "heard", "fixed", keep_empty=False),
        "snippets": _pairs(bundle.snippets, "trigger", "expansion", keep_empty=False),
        "templates": _pairs(bundle.templates, "name", "body", keep_empty=False),
    }
    profile = {k: v for k, v in bundle.profile.items() if k in ("field", "app") and v}
    if profile:
        data["profile"] = profile
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def export_text(vocabulary: list[str], pairs: list[Pair]) -> str:
    """The word lists alone (kept for callers that only have those)."""
    return export_bundle(Bundle(vocabulary=vocabulary, replacements=pairs))


def _read_pairs(data: dict, key: str, first: str, second: str, keep_empty: bool) -> list[Pair]:
    found = []
    for item in data.get(key) or []:
        if not isinstance(item, dict):
            continue
        a, b = item.get(first), item.get(second, "")
        if not (isinstance(a, str) and a.strip() and isinstance(b, str)):
            continue
        if not keep_empty and not b.strip():
            continue
        found.append((a.strip(), b if second in ("expansion", "body") else b.strip()))
    return found


def parse_file(text: str) -> Bundle:
    """Everything in an exported file, or the replacements in a plain text
    list. Raises ValueError when the file holds neither."""
    stripped = text.lstrip("﻿").strip()
    if not stripped.startswith("{"):
        pairs = parse_replacements_text(stripped)
        if not pairs:
            raise ValueError(
                'No word list found. Expected a VoxScribe export or "heard => replacement" lines.'
            )
        return Bundle(replacements=pairs)
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
    profile = data.get("profile")
    return Bundle(
        vocabulary=vocabulary,
        replacements=_read_pairs(data, "replacements", "heard", "replacement", True),
        learned=_read_pairs(data, "learned", "heard", "fixed", False),
        snippets=_read_pairs(data, "snippets", "trigger", "expansion", False),
        templates=_read_pairs(data, "templates", "name", "body", False),
        profile={
            k: v
            for k, v in (profile.items() if isinstance(profile, dict) else ())
            if k in ("field", "app") and isinstance(v, str) and v
        },
    )


def parse_import(text: str) -> tuple[list[str], list[Pair]]:
    """(vocabulary, replacements) read from an exported file or a plain text list."""
    bundle = parse_file(text)
    return bundle.vocabulary, bundle.replacements


def merge_replacements(existing: list[Pair], incoming: list[Pair]) -> tuple[list[Pair], int, int]:
    """(merged, added, changed). An incoming rule for the same key (any case)
    replaces the existing one in place, so two rules never fight; new rules go
    at the end in file order. Used for replacements, snippets and templates."""
    merged = list(existing)
    index_of = {key.strip().lower(): i for i, (key, _) in enumerate(merged)}
    added = changed = 0
    for key, value in incoming:
        lowered = key.strip().lower()
        if lowered in index_of:
            i = index_of[lowered]
            if merged[i] != (key, value):
                if merged[i][1] != value:
                    changed += 1
                merged[i] = (key, value)
        else:
            index_of[lowered] = len(merged)
            merged.append((key, value))
            added += 1
    return merged, added, changed
