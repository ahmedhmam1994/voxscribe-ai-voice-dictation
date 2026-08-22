"""Tests for core/settings.py's hotkey persistence.

QSettings normally writes to the Windows registry -- redirected to a
throwaway ini file per test (via monkeypatching `_settings`) so these don't
read or pollute the real VoxScribe registry key.
"""

from PySide6.QtCore import QSettings

import core.settings as settings


def _use_temp_settings(monkeypatch, tmp_path):
    ini_path = str(tmp_path / "settings.ini")
    monkeypatch.setattr(
        settings, "_settings", lambda: QSettings(ini_path, QSettings.Format.IniFormat)
    )


def test_default_hotkey_when_nothing_stored(monkeypatch, tmp_path):
    _use_temp_settings(monkeypatch, tmp_path)
    assert settings.get_hotkey() == settings.DEFAULT_HOTKEY


def test_set_then_get_round_trips(monkeypatch, tmp_path):
    _use_temp_settings(monkeypatch, tmp_path)
    settings.set_hotkey("f5")
    assert settings.get_hotkey() == "f5"


def test_get_rejects_value_outside_curated_list(monkeypatch, tmp_path):
    _use_temp_settings(monkeypatch, tmp_path)
    # Simulate a corrupted/hand-edited registry value -- must fall back to
    # the default rather than register an arbitrary global hotkey (e.g. a
    # letter key that would break typing everywhere).
    settings._settings().setValue("hotkey", "a")
    assert settings.get_hotkey() == settings.DEFAULT_HOTKEY


def test_available_hotkeys_contains_no_typing_keys():
    letters_and_digits = set("abcdefghijklmnopqrstuvwxyz0123456789")
    for key in settings.AVAILABLE_HOTKEYS:
        assert key not in letters_and_digits
        assert key != "space"


def test_default_hotkey_is_in_available_list():
    assert settings.DEFAULT_HOTKEY in settings.AVAILABLE_HOTKEYS
