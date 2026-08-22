"""Persisted user settings (QSettings-backed, Windows registry under the
hood). Currently just the global hold-to-talk hotkey.

The available choices are curated to F-keys and a few rarely-typed keys
rather than allowing an arbitrary key: since this is a *global* hold-to-talk
hotkey (registered system-wide, not just while VoxScribe has focus), letting
it land on a normal typing key (a letter, digit, space, etc.) would make
that key stop working for typing anywhere on the system while VoxScribe is
running.
"""

from __future__ import annotations

from PySide6.QtCore import QSettings

DEFAULT_HOTKEY = "f9"

AVAILABLE_HOTKEYS = [
    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
    "pause", "scroll lock", "insert",
]


def _settings() -> QSettings:
    return QSettings("VoxScribe", "VoxScribe")


def get_hotkey() -> str:
    value = _settings().value("hotkey", DEFAULT_HOTKEY)
    return value if value in AVAILABLE_HOTKEYS else DEFAULT_HOTKEY


def set_hotkey(key: str) -> None:
    _settings().setValue("hotkey", key)
