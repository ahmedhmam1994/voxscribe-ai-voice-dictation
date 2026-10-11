"""Tests for core/templates.py: spoken triggers and slot filling."""

from datetime import datetime

from PySide6.QtCore import QSettings

import core.templates as templates
from core.templates import Template, TemplateSession, find_template, slot_names

BUG = Template("bug report", "Title: {title}\nSteps: {steps}\nFiled {date}")
NOW = datetime(2026, 10, 11, 9, 5)


def _use_temp_settings(monkeypatch, tmp_path):
    ini_path = str(tmp_path / "settings.ini")
    monkeypatch.setattr(
        templates, "_settings", lambda: QSettings(ini_path, QSettings.Format.IniFormat)
    )


def test_slots_skip_date_and_time_and_repeats():
    assert slot_names("{title} {date} {time} {steps} {title}") == ["title", "steps"]


def test_both_trigger_words_find_the_template():
    assert find_template("Template bug report.", [BUG]) == BUG
    assert find_template("fill bug report", [BUG]) == BUG


def test_a_trigger_inside_a_sentence_is_not_a_template():
    assert find_template("please fill bug report now", [BUG]) is None


def test_an_unknown_name_finds_nothing():
    assert find_template("template invoice", [BUG]) is None


def test_session_asks_slots_in_order_and_renders():
    session = TemplateSession(BUG, now=NOW)
    assert session.prompt == "title"
    session.feed("Login fails.")
    assert session.prompt == "steps"
    session.feed("Open the app, then tap sign in. It crashes.")
    assert session.finished
    assert session.result() == (
        "Title: Login fails\nSteps: Open the app, then tap sign in. It crashes.\n"
        "Filed 2026-10-11"
    )


def test_skip_leaves_the_slot_empty():
    session = TemplateSession(BUG, now=NOW)
    assert session.feed("skip") == "skip"
    session.feed("Some steps")
    assert session.result().startswith("Title: \nSteps: Some steps")


def test_cancel_is_reported():
    session = TemplateSession(BUG, now=NOW)
    assert session.feed("Cancel.") == "cancel"


def test_templates_round_trip_through_settings(monkeypatch, tmp_path):
    _use_temp_settings(monkeypatch, tmp_path)
    templates.set_templates([BUG, Template("  ", "ignored"), Template("empty", "")])

    assert templates.get_templates() == [BUG]


def test_settings_text_round_trips_with_line_breaks():
    items = [Template("bug report", "Title: {title}\nSteps: {steps}"), Template("hi", "Hello")]

    assert templates.parse_lines(templates.format_lines(items)) == items


def test_parsing_skips_lines_without_a_name_or_body():
    text = "no arrow here\n => only a body\nname only =>\nok => fine"

    assert templates.parse_lines(text) == [Template("ok", "fine")]
