"""Tests for core/modes.py."""

from core.modes import drop_final_period, effective_options, mode_for_app


def test_free_uses_the_global_mode_everywhere():
    assert mode_for_app("slack.exe", {}, "notes", True, is_pro=False) == "notes"


def test_free_cannot_use_code_mode():
    assert mode_for_app("code.exe", {}, "code", True, is_pro=False) == "default"


def test_pro_switches_by_app():
    assert mode_for_app("Slack.exe", {}, "default", True, is_pro=True) == "chat"
    assert mode_for_app("OUTLOOK.EXE", {}, "default", True, is_pro=True) == "email"
    assert mode_for_app("code.exe", {}, "default", True, is_pro=True) == "code"


def test_pro_without_auto_switch_keeps_the_global_mode():
    assert mode_for_app("slack.exe", {}, "email", False, is_pro=True) == "email"


def test_unknown_app_uses_the_global_mode():
    assert mode_for_app("game.exe", {}, "notes", True, is_pro=True) == "notes"


def test_profile_mode_beats_auto_switch():
    assert mode_for_app("slack.exe", {"mode": "notes"}, "default", True, is_pro=True) == "notes"


def test_profile_options_override_the_mode():
    mode, options = effective_options(
        "slack.exe", {"smart": False, "language": "ar"}, "default", True, is_pro=True
    )
    assert mode == "chat"
    assert options["smart"] is False
    assert options["language"] == "ar"
    assert options["period"] is False


def test_free_ignores_profiles():
    mode, options = effective_options("slack.exe", {"smart": False}, "chat", True, is_pro=False)
    assert mode == "chat"
    assert options["smart"] is True


def test_default_mode_changes_nothing():
    assert effective_options("x.exe", {}, "default", False, is_pro=False) == ("default", {})


def test_drop_final_period_single_sentence():
    assert drop_final_period("See you at 5.") == "See you at 5"


def test_drop_final_period_keeps_multi_sentence_messages():
    text = "Running late. See you at 5."
    assert drop_final_period(text) == text


def test_drop_final_period_leaves_ellipsis_and_abbreviations():
    assert drop_final_period("Well...") == "Well..."
    assert drop_final_period("Bring pens, paper, etc.") == "Bring pens, paper, etc."


def test_drop_final_period_leaves_questions():
    assert drop_final_period("Are you coming?") == "Are you coming?"
