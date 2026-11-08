"""Tests for core/file_library.py (recent file and link transcripts)."""

import time

from core import file_library as lib


def test_added_entries_come_back_newest_first(tmp_path):
    a = lib.add("talk.mp3", "C:/a/talk.mp3", lib.KIND_FILE, "first text", folder=tmp_path)
    time.sleep(0.01)
    b = lib.add("Video [x]", "https://youtu.be/x", lib.KIND_CAPTIONS, "second", folder=tmp_path)
    found = lib.recent(folder=tmp_path)
    assert [e.id for e in found] == [b.id, a.id]
    assert found[0].label == "Site captions" and found[1].label == "File"
    assert lib.get(a.id, folder=tmp_path).text == "first text"


def test_empty_text_is_not_kept(tmp_path):
    assert lib.add("x", "y", lib.KIND_FILE, "   ", folder=tmp_path) is None
    assert lib.recent(folder=tmp_path) == []


def test_unicode_survives(tmp_path):
    e = lib.add("محاضرة", "C:/x.mp3", lib.KIND_FILE, "نريد نظام حجز جديد", folder=tmp_path)
    assert lib.get(e.id, folder=tmp_path).text == "نريد نظام حجز جديد"
    assert e.words == 4


def test_delete_and_clear(tmp_path):
    a = lib.add("a", "a", lib.KIND_FILE, "one", folder=tmp_path)
    lib.add("b", "b", lib.KIND_LINK, "two", folder=tmp_path)
    lib.delete(a.id, folder=tmp_path)
    assert [e.title for e in lib.recent(folder=tmp_path)] == ["b"]
    lib.clear(folder=tmp_path)
    assert lib.recent(folder=tmp_path) == []


def test_ids_cannot_reach_outside_the_folder(tmp_path):
    outside = tmp_path / "secret.json"
    outside.write_text("{}")
    inner = tmp_path / "lib"
    lib.delete("../secret", folder=inner)
    assert outside.exists()
    assert lib.get("../secret", folder=inner) is None


def test_only_the_newest_are_kept(tmp_path, monkeypatch):
    monkeypatch.setattr(lib, "MAX_ENTRIES", 3)
    for i in range(5):
        lib.add(f"t{i}", "s", lib.KIND_FILE, f"text {i}", folder=tmp_path)
        time.sleep(0.002)
    assert [e.title for e in lib.recent(folder=tmp_path)] == ["t4", "t3", "t2"]


def test_damaged_files_are_skipped(tmp_path):
    lib.add("ok", "s", lib.KIND_FILE, "fine", folder=tmp_path)
    (tmp_path / "9999999999999-bad.json").write_text("{not json", encoding="utf-8")
    assert [e.title for e in lib.recent(folder=tmp_path)] == ["ok"]


def test_when_reads_naturally():
    now = time.mktime((2026, 11, 8, 15, 0, 0, 0, 0, -1))
    entry = lambda t: lib.Entry("i", "t", "s", "file", t, "x")  # noqa: E731
    assert lib.when(entry(now - 3600), now).startswith("Today 2:00")
    assert lib.when(entry(now - 86400), now).startswith("Yesterday 3:00")
    assert lib.when(entry(now - 4 * 86400), now).startswith("4 Nov")
