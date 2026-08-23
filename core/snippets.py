"""Snippets/macros -- a Pro feature (see core/license.py): speak a short
trigger phrase, get a longer piece of boilerplate text typed instead (an
email sign-off, a canned response, etc). Entirely local pattern-matching,
no LLM call.

Stored as JSON (not the comma-joined-string pattern core/settings.py uses
for simple lists like custom vocabulary) since an expansion is arbitrary
free text that can legitimately contain commas -- comma-splitting would
corrupt it.
"""

from __future__ import annotations

import json

from PySide6.QtCore import QSettings


def _settings() -> QSettings:
    return QSettings("VoxScribe", "VoxScribe")


def get_snippets() -> list[tuple[str, str]]:
    """(trigger, expansion) pairs, in the order they were added."""
    raw = _settings().value("snippets", "")
    if not raw:
        return []
    try:
        pairs = json.loads(raw)
    except ValueError:
        return []
    return [(str(t), str(e)) for t, e in pairs if isinstance(t, str) and isinstance(e, str)]


def set_snippets(pairs: list[tuple[str, str]]) -> None:
    cleaned = [(t.strip(), e) for t, e in pairs if t.strip()]
    _settings().setValue("snippets", json.dumps(cleaned))


def expand_snippet(text: str) -> str:
    """If `text` (after trimming/case-folding) exactly matches a trigger
    phrase, returns its expansion. Otherwise returns `text` unchanged.
    Exact-match on the whole utterance, not a substring replace -- matches
    how a spoken trigger is actually used: say the trigger alone, get the
    expansion in its place."""
    normalized = text.strip().strip(".!?").lower()
    for trigger, expansion in get_snippets():
        if trigger.strip().lower() == normalized:
            return expansion
    return text
