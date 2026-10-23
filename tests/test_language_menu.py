"""Tests for app/language_menu.py, the tray menu's language submenu. Qt runs
headless (offscreen), and the language itself lives in a plain dict, so nothing
touches the registry or a real screen."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import QObject  # noqa: E402
from PySide6.QtWidgets import QApplication, QMenu  # noqa: E402

from app.language_menu import LanguageMenu  # noqa: E402
from core import settings as app_settings  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _build(qapp, current="en", on_changed=None):
    state = {"language": current}
    owner = QObject()
    menu = QMenu()
    languages = [(None, "Auto-detect"), ("en", "English"), ("ar", "Arabic")]
    language_menu = LanguageMenu(
        owner,
        menu,
        languages,
        lambda: state["language"],
        lambda code: state.__setitem__("language", code),
        on_changed=on_changed,
    )
    # The owner and menu must outlive the test body, so they ride on the menu object.
    language_menu._keep = (owner, menu)
    return language_menu, state


def _checked(language_menu):
    return [a.text() for a in language_menu.submenu.actions() if a.isChecked()]


def test_the_language_in_use_is_ticked(qapp):
    language_menu, _ = _build(qapp, "ar")

    assert _checked(language_menu) == ["Arabic"]


def test_auto_detect_is_ticked_when_there_is_no_language(qapp):
    language_menu, _ = _build(qapp, None)

    assert _checked(language_menu) == ["Auto-detect"]


def test_choosing_a_language_saves_it_and_ticks_it(qapp):
    seen = []
    language_menu, state = _build(qapp, "en", on_changed=lambda code, name: seen.append((code, name)))

    language_menu.choose("ar")

    assert state["language"] == "ar"
    assert _checked(language_menu) == ["Arabic"]
    assert seen == [("ar", "Arabic")]


def test_choosing_the_current_language_changes_nothing(qapp):
    seen = []
    language_menu, state = _build(qapp, "en", on_changed=lambda code, name: seen.append(code))

    language_menu.choose("en")

    assert state["language"] == "en"
    assert seen == []
    assert _checked(language_menu) == ["English"]


def test_a_change_made_elsewhere_is_picked_up_by_sync(qapp):
    language_menu, state = _build(qapp, "en")
    state["language"] = None

    language_menu.sync()

    assert _checked(language_menu) == ["Auto-detect"]


def test_the_menu_lists_every_language_the_app_offers(qapp):
    owner = QObject()
    menu = QMenu()
    language_menu = LanguageMenu(
        owner, menu, app_settings.AVAILABLE_LANGUAGES, lambda: "en", lambda code: None
    )

    texts = [a.text() for a in language_menu.submenu.actions()]

    assert texts == [name for _, name in app_settings.AVAILABLE_LANGUAGES]
    assert "Arabic" in texts
