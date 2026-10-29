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


def test_telemetry_defaults_on_and_can_be_switched_off(monkeypatch, tmp_path):
    _use_temp_settings(monkeypatch, tmp_path)
    assert settings.get_telemetry_enabled() is True
    settings.set_telemetry_enabled(False)
    assert settings.get_telemetry_enabled() is False
    settings.set_telemetry_enabled(True)
    assert settings.get_telemetry_enabled() is True


def test_typing_delay_default_and_clamping(monkeypatch, tmp_path):
    _use_temp_settings(monkeypatch, tmp_path)
    assert settings.get_typing_delay_ms() == 30
    settings.set_typing_delay_ms(80)
    assert settings.get_typing_delay_ms() == 80
    settings.set_typing_delay_ms(5000)
    assert settings.get_typing_delay_ms() == settings.MAX_TYPING_DELAY_MS
    settings.set_typing_delay_ms(1)
    assert settings.get_typing_delay_ms() == settings.MIN_TYPING_DELAY_MS


def test_typing_delay_ignores_garbage_values(monkeypatch, tmp_path):
    _use_temp_settings(monkeypatch, tmp_path)
    settings._settings().setValue("typing_delay_ms", "not a number")
    assert settings.get_typing_delay_ms() == settings.DEFAULT_TYPING_DELAY_MS


def test_batch_trials_run_out_after_two(monkeypatch, tmp_path):
    _use_temp_settings(monkeypatch, tmp_path)
    assert settings.get_batch_trials_left() == 2
    assert settings.use_batch_trial() == 1
    assert settings.use_batch_trial() == 0
    assert settings.use_batch_trial() == 0
    assert settings.get_batch_trials_left() == 0


def test_caption_line_chars_default_range_and_off(monkeypatch, tmp_path):
    _use_temp_settings(monkeypatch, tmp_path)
    assert settings.get_caption_line_chars() == 42
    settings.set_caption_line_chars(0)
    assert settings.get_caption_line_chars() == 0
    settings.set_caption_line_chars(500)
    assert settings.get_caption_line_chars() == settings.MAX_CAPTION_LINE_CHARS


def test_a_profiles_packs_replace_the_enabled_ones(monkeypatch):
    monkeypatch.setattr(settings, "get_enabled_packs", lambda: ["business"])
    monkeypatch.setattr(settings, "get_custom_vocabulary", lambda: [])
    default = settings.correction_terms()
    assert "EBITDA" in default and "metformin" not in default
    medical_only = settings.correction_terms(["medical"])
    assert "metformin" in medical_only and "EBITDA" not in medical_only
    assert settings.correction_terms([]) == []
    assert settings.correction_fuzzy_terms([]) == []
    assert "metformin" in settings.correction_fuzzy_terms(["medical"])
    assert settings.custom_vocabulary_prompt([]) is None
    assert "metformin" in settings.custom_vocabulary_prompt(["medical"])


def test_new_option_defaults_and_inbox_hotkey_rules(monkeypatch, tmp_path):
    from PySide6.QtCore import QSettings

    ini = str(tmp_path / "s.ini")
    monkeypatch.setattr(settings, "_settings", lambda: QSettings(ini, QSettings.Format.IniFormat))
    assert not settings.get_spoken_formats_enabled()
    assert not settings.get_read_back_enabled()
    assert not settings.get_mark_unsure_words()
    assert not settings.get_startup_prompt_done()
    assert settings.get_inbox_hotkey() == ""
    assert settings.get_inbox_path().endswith("VoxScribe Inbox.md")
    settings.set_spoken_formats_enabled(True)
    settings.set_read_back_enabled(True)
    settings.set_mark_unsure_words(True)
    settings.set_startup_prompt_done()
    assert settings.get_spoken_formats_enabled()
    assert settings.get_read_back_enabled()
    assert settings.get_mark_unsure_words()
    assert settings.get_startup_prompt_done()
    settings.set_inbox_hotkey("left shift")  # needs the hold delay: refused
    assert settings.get_inbox_hotkey() == ""
    settings.set_inbox_hotkey("f8")
    assert settings.get_inbox_hotkey() == "f8"
    settings.set_inbox_path("  D:/vault/Inbox.md ")
    assert settings.get_inbox_path() == "D:/vault/Inbox.md"


def test_meeting_settings_defaults_and_changes(monkeypatch, tmp_path):
    from PySide6.QtCore import QSettings

    ini = str(tmp_path / "m.ini")
    monkeypatch.setattr(settings, "_settings", lambda: QSettings(ini, QSettings.Format.IniFormat))
    assert settings.get_meeting_folder().endswith("VoxScribe Meetings")
    assert settings.get_meeting_loopback() is True
    settings.set_meeting_folder("  D:/vault/Meetings ")
    settings.set_meeting_loopback(False)
    assert settings.get_meeting_folder() == "D:/vault/Meetings"
    assert settings.get_meeting_loopback() is False
