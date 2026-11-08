"""The same cases as the Android app's LearnedWordsTest, so both learn alike."""

from PySide6.QtCore import QSettings

from core import learned_words, replacements
from core.learned_words import Fix

COMMON = {
    "tell", "will", "call", "you", "at", "five", "the", "order", "on", "tuesday", "wednesday",
    "meet", "there", "their", "see", "great", "grate", "hi", "is", "ready", "any", "way", "anyway",
}  # fmt: skip


def fix(before, after, start=0):
    return learned_words.find_fix(before, after, start, COMMON)


def _temp_settings(monkeypatch, tmp_path):
    ini = str(tmp_path / "settings.ini")
    store = lambda: QSettings(ini, QSettings.Format.IniFormat)  # noqa: E731
    monkeypatch.setattr(learned_words, "_settings", store)
    monkeypatch.setattr(replacements, "_settings", store)


def test_a_misheard_name_fixed_by_hand_is_learned():
    assert fix("Tell Shivon hi", "Tell Siobhan hi") == Fix("Shivon", "Siobhan")
    assert fix("Call Katerina at five", "Call Kateryna at five") == Fix("Katerina", "Kateryna")


def test_a_casing_fix_and_a_join_are_learned():
    assert fix("the voxscribe order", "the VoxScribe order") == Fix("voxscribe", "VoxScribe")
    assert fix("the vox scribe order", "the VoxScribe order") == Fix("vox scribe", "VoxScribe")


def test_changing_what_you_meant_is_not_learned():
    assert fix("Meet on Tuesday", "Meet on Wednesday") is None
    assert fix("see you there", "see you their") is None
    assert fix("Tell Sarah hi", "Tell Emily hi") is None


def test_only_a_clear_one_word_fix_counts():
    assert fix("Tell Shivon hi", "Tell Shivon hi and more") is None
    assert fix("Tell Shivon hi", "Tell Siobhan hello there") is None
    assert fix("Tell Shivon hi", "Tell S hi") is None
    assert fix("Tell Shivon hi", "") is None


def test_text_that_was_there_before_the_dictation_is_not_learned_from():
    before = "Dear Shivon, the order is ready"
    assert fix(before, "Dear Siobhan, the order is ready", 12) is None
    assert fix(before, "Dear Siobhan, the order is ready", 0) == Fix("Shivon", "Siobhan")


def test_a_fix_of_a_half_typed_fix_becomes_one_fix():
    first = learned_words.add([], Fix("Shivon", "Sio"))
    assert learned_words.add(first, Fix("Sio", "Siobhan")) == [Fix("Shivon", "Siobhan")]


def test_fixing_a_learned_word_back_forgets_it():
    assert learned_words.add([Fix("Shivon", "Siobhan")], Fix("Siobhan", "Shivon")) == []


def test_the_same_heard_word_keeps_only_the_newest_fix():
    assert learned_words.add([Fix("Ahmed", "Ahmad")], Fix("ahmed", "Ahmet")) == [
        Fix("ahmed", "Ahmet")
    ]


def test_everyday_words_and_their_plain_forms_are_common():
    common = learned_words.common_words()
    assert len(common) > 15000
    assert "house" in common and "siobhan" not in common
    assert learned_words.is_common("meetings", common)
    assert learned_words.is_common("running", common)


def test_learned_fixes_apply_after_your_own_replacements(monkeypatch, tmp_path):
    _temp_settings(monkeypatch, tmp_path)
    assert learned_words.remember(Fix("Shivon", "Siobhan")) == Fix("Shivon", "Siobhan")
    assert replacements.apply_replacements("Tell shivon hi") == "Tell Siobhan hi"
    replacements.set_replacements([("shivon", "Siobhan O'Neil")])
    assert replacements.apply_replacements("Tell shivon hi") == "Tell Siobhan O'Neil hi"


def test_learning_can_be_turned_off_and_fixes_removed(monkeypatch, tmp_path):
    _temp_settings(monkeypatch, tmp_path)
    learned_words.remember(Fix("Shivon", "Siobhan"))
    learned_words.set_enabled(False)
    assert replacements.apply_replacements("Tell shivon hi") == "Tell shivon hi"
    learned_words.set_enabled(True)
    learned_words.forget("shivon")
    assert learned_words.all_fixes() == []


def test_remember_returns_none_when_it_only_undid_a_fix(monkeypatch, tmp_path):
    _temp_settings(monkeypatch, tmp_path)
    learned_words.remember(Fix("Shivon", "Siobhan"))
    assert learned_words.remember(Fix("Siobhan", "Shivon")) is None
    assert learned_words.all_fixes() == []


def test_the_list_keeps_the_newest_two_hundred(monkeypatch, tmp_path):
    fixes = []
    for i in range(learned_words.MAX + 5):
        fixes = learned_words.add(fixes, Fix(f"Name{i}x", f"Name{i}y"))
    assert len(fixes) == learned_words.MAX
    assert fixes[-1] == Fix(f"Name{learned_words.MAX + 4}x", f"Name{learned_words.MAX + 4}y")
