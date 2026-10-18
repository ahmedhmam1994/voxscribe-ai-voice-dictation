"""Tests for core/redo.py's choice of model for Try harder."""

from core.redo import pick_redo_model

ALL = {"tiny", "base", "small", "medium", "large-v3-turbo", "large"}


def test_free_user_on_tiny_redoes_with_small():
    assert pick_redo_model("tiny", False, ALL) == ("small", True)


def test_free_user_on_small_redoes_small_carefully():
    assert pick_redo_model("small", False, ALL) == ("small", False)


def test_pro_prefers_large_turbo():
    assert pick_redo_model("small", True, ALL) == ("large-v3-turbo", True)


def test_pro_falls_back_to_what_is_downloaded():
    assert pick_redo_model("small", True, {"small", "medium"}) == ("medium", True)


def test_on_large_turbo_without_large_redoes_turbo_carefully():
    assert pick_redo_model("large-v3-turbo", True, {"large-v3-turbo"}) == (
        "large-v3-turbo",
        False,
    )


def test_on_large_turbo_with_large_downloaded_uses_large():
    assert pick_redo_model("large-v3-turbo", True, ALL) == ("large", True)


def test_already_on_large_redoes_carefully():
    assert pick_redo_model("large", True, ALL) == ("large", False)


def test_nothing_bigger_downloaded_redoes_carefully():
    assert pick_redo_model("base", False, {"tiny", "base"}) == ("base", False)
