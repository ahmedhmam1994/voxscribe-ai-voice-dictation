"""Changelog text shown once in-app after an update, so users who never
read GitHub release notes still find out what changed. Deliberately a
small hardcoded dict, not fetched from the GitHub API -- this has to work
fully offline, consistent with the rest of the app (see AGENTS.md's "no
cloud calls" note), and the text only needs to exist for versions someone
could realistically be upgrading from.
"""

from __future__ import annotations

WHATS_NEW: dict[str, str] = {
    "1.6.3.1": (
        "- New: say \"scratch that\" alone to undo the last thing VoxScribe typed "
        "(with Voice commands enabled in Settings).\n"
        "- Real icons throughout the app, replacing the old hand-drawn ones."
    ),
    "1.6.3": (
        "- New look: green waveform icon and accent color throughout the app.\n"
        "- Fixed: the Settings window could overflow and clip its fields on some "
        "displays."
    ),
    "1.6.2": (
        "- Voice commands (opt-in): say \"period\", \"comma\", \"new line\" and more "
        "while dictating to get real punctuation instead of the literal words. "
        "Off by default in Settings.\n"
        "- Fixed: dictated text could type into the wrong window if you switched "
        "apps while a transcription was still finishing."
    ),
}


def whats_new_text(version: str) -> str | None:
    return WHATS_NEW.get(version)
