from PySide6.QtCore import QSettings

from core import settings, voice_profile


def _temp_settings(monkeypatch, tmp_path):
    ini = str(tmp_path / "settings.ini")
    store = lambda: QSettings(ini, QSettings.Format.IniFormat)  # noqa: E731
    monkeypatch.setattr(settings, "_settings", store)
    monkeypatch.setattr(voice_profile, "_settings", store)


def test_nothing_is_picked_before_the_question_is_answered(monkeypatch, tmp_path):
    _temp_settings(monkeypatch, tmp_path)
    assert voice_profile.get_field() is None


def test_medical_turns_on_the_pack_and_spoken_formats(monkeypatch, tmp_path):
    _temp_settings(monkeypatch, tmp_path)
    voice_profile.apply_field("medical")
    assert voice_profile.get_field() == "medical"
    assert settings.get_enabled_packs() == ["medical"]
    assert settings.get_spoken_formats_enabled() is True


def test_switching_field_swaps_only_the_field_pack(monkeypatch, tmp_path):
    _temp_settings(monkeypatch, tmp_path)
    settings.set_enabled_packs(["user:clinic", "medical"])
    voice_profile.apply_field("legal")
    assert settings.get_enabled_packs() == ["user:clinic", "legal"]
    voice_profile.apply_field("everyday")
    assert settings.get_enabled_packs() == ["user:clinic"]


def test_code_turns_on_code_dictation(monkeypatch, tmp_path):
    _temp_settings(monkeypatch, tmp_path)
    voice_profile.apply_field("code")
    assert settings.get_code_dictation_enabled() is True


def test_an_unknown_answer_falls_back_to_everyday(monkeypatch, tmp_path):
    _temp_settings(monkeypatch, tmp_path)
    assert voice_profile.apply_field("astronaut").id == "everyday"
    assert voice_profile.get_field() == "everyday"


def test_where_you_write_sets_the_dictation_mode(monkeypatch, tmp_path):
    _temp_settings(monkeypatch, tmp_path)
    assert voice_profile.get_app() is None
    voice_profile.apply_app("chat")
    assert voice_profile.get_app() == "chat"
    assert settings.get_mode() == "chat"
    voice_profile.apply_app("mixed")
    assert settings.get_mode() == "default"


def test_every_app_choice_names_a_real_mode():
    from core.modes import MODES

    assert all(choice.mode in MODES for choice in voice_profile.APPS)
