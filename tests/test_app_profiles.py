"""Tests for core/app_profiles.py: per-app setting overrides."""

from PySide6.QtCore import QSettings

import core.app_profiles as app_profiles


def _use_temp_settings(monkeypatch, tmp_path):
    ini_path = str(tmp_path / "settings.ini")
    monkeypatch.setattr(
        app_profiles, "_settings", lambda: QSettings(ini_path, QSettings.Format.IniFormat)
    )


def test_a_line_sets_flags_and_a_language():
    parsed = app_profiles.parse_lines("Code.exe => code=on, cleanup=off, language=ar")

    assert parsed == {"code.exe": {"code": True, "cleanup": False, "language": "ar"}}


def test_auto_means_no_language_forced():
    assert app_profiles.parse_lines("chat.exe => language=auto") == {
        "chat.exe": {"language": None}
    }


def test_bad_lines_options_and_values_are_dropped():
    text = "no arrow\n => code=on\nx.exe => speed=fast, cleanup=maybe\ny.exe => smart=yes"

    assert app_profiles.parse_lines(text) == {"y.exe": {"smart": True}}


def test_lines_round_trip():
    profiles = {"code.exe": {"code": True, "language": "en"}, "chat.exe": {"language": None}}

    assert app_profiles.parse_lines(app_profiles.format_lines(profiles)) == profiles


def test_profiles_are_stored_and_looked_up_by_name(monkeypatch, tmp_path):
    _use_temp_settings(monkeypatch, tmp_path)
    app_profiles.set_profiles({"code.exe": {"code": True}})

    assert app_profiles.profile_for("CODE.EXE") == {"code": True}
    assert app_profiles.profile_for("other.exe") == {}
    assert app_profiles.profile_for(None) == {}


def test_packs_option_picks_packs_or_none():
    profiles = app_profiles.parse_lines(
        "winword.exe => packs=legal\nepic.exe => packs=medical+business\nslack.exe => packs=off"
    )
    assert profiles["winword.exe"] == {"packs": ["legal"]}
    assert profiles["epic.exe"] == {"packs": ["medical", "business"]}
    assert profiles["slack.exe"] == {"packs": []}


def test_unknown_pack_name_drops_the_option():
    assert app_profiles.parse_lines("a.exe => packs=medical+nope, cleanup=off") == {
        "a.exe": {"cleanup": False}
    }


def test_packs_round_trip():
    text = "epic.exe => packs=medical+legal\nslack.exe => packs=off"
    assert app_profiles.format_lines(app_profiles.parse_lines(text)) == text
