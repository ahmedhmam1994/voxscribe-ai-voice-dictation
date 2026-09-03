"""Tests for core/snippets.py: trigger matching and template-variable
expansion. QSettings redirected to a throwaway ini file per test, same
pattern as tests/test_settings.py.
"""

from datetime import datetime

from PySide6.QtCore import QSettings

import core.snippets as snippets


def _use_temp_settings(monkeypatch, tmp_path):
    ini_path = str(tmp_path / "settings.ini")
    monkeypatch.setattr(
        snippets, "_settings", lambda: QSettings(ini_path, QSettings.Format.IniFormat)
    )


def test_no_snippets_returns_text_unchanged(monkeypatch, tmp_path):
    _use_temp_settings(monkeypatch, tmp_path)
    assert snippets.expand_snippet("hello there") == "hello there"


def test_exact_trigger_match_expands(monkeypatch, tmp_path):
    _use_temp_settings(monkeypatch, tmp_path)
    snippets.set_snippets([("sig", "Best, Ahmed")])
    assert snippets.expand_snippet("sig") == "Best, Ahmed"


def test_non_matching_text_left_unchanged(monkeypatch, tmp_path):
    _use_temp_settings(monkeypatch, tmp_path)
    snippets.set_snippets([("sig", "Best, Ahmed")])
    assert snippets.expand_snippet("this is a sig test") == "this is a sig test"


def test_trigger_matching_is_case_and_punctuation_insensitive(monkeypatch, tmp_path):
    _use_temp_settings(monkeypatch, tmp_path)
    snippets.set_snippets([("sig", "Best, Ahmed")])
    assert snippets.expand_snippet("Sig.") == "Best, Ahmed"


def test_date_template_variable_is_filled_in(monkeypatch, tmp_path):
    _use_temp_settings(monkeypatch, tmp_path)
    snippets.set_snippets([("today", "Today is {date}")])
    expected = datetime.now().strftime("%Y-%m-%d")
    assert snippets.expand_snippet("today") == f"Today is {expected}"


def test_time_template_variable_is_filled_in(monkeypatch, tmp_path):
    _use_temp_settings(monkeypatch, tmp_path)
    snippets.set_snippets([("now", "It's {time}")])
    expected = datetime.now().strftime("%H:%M")
    assert snippets.expand_snippet("now") == f"It's {expected}"


def test_clipboard_template_variable_falls_back_to_empty_without_qapplication(
    monkeypatch, tmp_path
):
    _use_temp_settings(monkeypatch, tmp_path)
    snippets.set_snippets([("paste", "You copied: {clipboard}")])
    # No QApplication instance exists in this test process, so the
    # clipboard placeholder should degrade to empty rather than raise.
    assert snippets.expand_snippet("paste") == "You copied: "
