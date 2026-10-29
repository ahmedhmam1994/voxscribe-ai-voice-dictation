"""Tests for app/theme.py: the dark-to-light colour table and its rules."""

import pytest

from app import theme


def test_no_light_value_is_also_a_dark_key():
    # A light value that is also a dark key would be swapped twice.
    assert not set(v.lower() for v in theme._LIGHT.values()) & set(k.lower() for k in theme._LIGHT)


def test_every_key_is_a_plain_hex_colour():
    for dark, light in theme._LIGHT.items():
        assert len(dark) == 7 and dark.startswith("#")
        assert len(light) == 7 and light.startswith("#")


@pytest.fixture
def light(monkeypatch):
    monkeypatch.setattr(theme, "_light", True)


@pytest.fixture
def dark(monkeypatch):
    monkeypatch.setattr(theme, "_light", False)


def test_dark_leaves_everything_alone(dark):
    css = "QWidget { color: #eceef4; background: #121319; }"
    assert theme.t(css) == css
    assert theme.hx("#3ecf8e") == "#3ecf8e"


def test_light_swaps_listed_colours_and_nothing_else(light):
    css = "QWidget { color: #ECEEF4; background: #121319; border: 1px solid #123456; }"
    assert theme.t(css) == "QWidget { color: #1c1e29; background: #f3f4f8; border: 1px solid #123456; }"
    assert theme.hx("#3ecf8e") == "#17895a"
    assert theme.hx("#ffffff") == "#ffffff"


def test_light_swap_is_applied_once(light):
    once = theme.t("color: #8b8d9c;")
    assert theme.t(once) == once


def test_appearance_setting_defaults_to_dark_and_rejects_junk(monkeypatch):
    from core import settings

    store = {}

    class FakeSettings:
        def value(self, key, default=None):
            return store.get(key, default)

        def setValue(self, key, value):  # noqa: N802
            store[key] = value

    monkeypatch.setattr(settings, "_settings", lambda: FakeSettings())
    assert settings.get_appearance() == "dark"
    settings.set_appearance("light")
    assert settings.get_appearance() == "light"
    settings.set_appearance("purple")
    assert settings.get_appearance() == "dark"
