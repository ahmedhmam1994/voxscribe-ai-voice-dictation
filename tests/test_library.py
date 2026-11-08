from datetime import datetime, timedelta
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from core import file_library, history, library, settings


@pytest.fixture
def stores(monkeypatch, tmp_path):
    ini = str(tmp_path / "settings.ini")
    store = lambda: QSettings(ini, QSettings.Format.IniFormat)  # noqa: E731
    monkeypatch.setattr(settings, "_settings", store)
    monkeypatch.setattr(library, "_settings", store)
    monkeypatch.setattr(history, "HISTORY_PATH", tmp_path / "history.json")
    monkeypatch.setattr(file_library, "LIBRARY_DIR", tmp_path / "files")
    settings._settings().setValue("inbox_path", str(tmp_path / "inbox.md"))
    settings._settings().setValue("meeting_folder", str(tmp_path / "meetings"))
    return tmp_path


def _old_dictation(text: str, days_ago: int) -> None:
    history.add_entry(text, 3.0)
    entries = history._load()
    entries[-1].timestamp = (datetime.now() - timedelta(days=days_ago)).isoformat(
        timespec="seconds"
    )
    history._save(entries)


def test_everything_shows_up_newest_first(stores):
    history.add_entry("Send the Henderson invoice on Monday", 4.0)
    file_library.add("call.mp3", "C:/call.mp3", file_library.KIND_FILE, "Henderson called back")
    (stores / "inbox.md").write_text(
        "# VoxScribe Inbox\n\n## 2026-10-28\n- 14:32 Ask Henderson about the lab\n",
        encoding="utf-8",
    )
    meetings = stores / "meetings"
    meetings.mkdir()
    (meetings / "2026-10-20 09-00 Meeting.md").write_text(
        "---\ntags: [meeting]\n---\n# Meeting 2026-10-20 09:00\n\nHenderson budget review\n",
        encoding="utf-8",
    )
    items = library.all_items()
    kinds = [i.kind for i in items]
    # The dictation and the file were made in the same second; the notes are older.
    assert set(kinds[:2]) == {"file", "dictation"}
    assert kinds[2:] == ["inbox", "meeting"]
    assert not items[-1].text.startswith("---")
    assert len(library.search(items, "henderson")) == 4


def test_search_needs_every_word_and_ignores_case(stores):
    history.add_entry("Send the Henderson invoice", 2.0)
    history.add_entry("Henderson called about lunch", 2.0)
    items = library.all_items()
    assert len(library.search(items, "HENDERSON invoice")) == 1
    assert library.search(items, "nothing like this") == []


def test_filters_by_type_and_date(stores):
    history.add_entry("today's note", 1.0)
    _old_dictation("an old note", 40)
    file_library.add("x.mp3", "x", file_library.KIND_LINK, "a link transcript")
    items = library.all_items()
    assert {i.kind for i in library.search(items, kind=library.KIND_FILE)} == {"file"}
    assert [i.text for i in library.search(items, kind="dictation", since_days=30)] == [
        "today's note"
    ]
    assert len(library.search(items, since_days=0)) == 2


def test_keep_for_is_forever_by_default(stores):
    _old_dictation("an old note", 400)
    assert library.get_keep_days() is None
    assert library.apply_retention() == 0
    assert len(library.all_items()) == 1


def test_keep_for_thirty_days_clears_old_words_but_keeps_counts(stores):
    _old_dictation("an old note", 40)
    history.add_entry("a new note", 1.0)
    library.set_keep_days(30)
    assert library.apply_retention() == 1
    assert [i.text for i in library.all_items()] == ["a new note"]
    assert len(history._load()) == 2  # Insights still counts both
    assert history._load()[0].words == 3


def test_keep_for_off_keeps_nothing_said(stores):
    history.add_entry("a note", 1.0)
    file_library.add("x.mp3", "x", file_library.KIND_FILE, "words")
    library.set_keep_days(library.KEEP_OFF)
    assert library.keeps_text() is False
    library.apply_retention()
    assert library.all_items() == []
    history.add_entry("secret", 1.0, keep_text=library.keeps_text())
    assert history._load()[-1].text == "" and history._load()[-1].words == 1


def test_delete_removes_dictations_and_files_but_never_your_notes(stores):
    history.add_entry("forget me", 1.0)
    file_library.add("x.mp3", "x", file_library.KIND_FILE, "and me")
    (stores / "inbox.md").write_text("## 2026-10-28\n- 09:00 keep me\n", encoding="utf-8")
    for item in library.all_items():
        library.delete(item)
    assert [i.text for i in library.all_items()] == ["keep me"]
    assert Path(stores / "inbox.md").read_text(encoding="utf-8").endswith("keep me\n")


def test_snippet_shows_the_words_around_the_match():
    item = library.Item("1", "dictation", "Dictation", "t", "a " * 100 + "Henderson b", datetime.now())
    piece = library.snippet(item, "henderson", width=40)
    assert "Henderson" in piece and piece.startswith("...")


def test_odd_meeting_file_names_are_skipped():
    assert library.meeting_item(Path("notes.md"), "x") is None
    item = library.meeting_item(Path("2026-11-01 14-05 Meeting (2).md"), "# hi\n")
    assert item.title == "Meeting 2026-11-01 14:05"


def test_snippets_of_notes_drop_markdown_and_cut_at_words():
    note = "# Meeting\n\n## Action items\n\n- [ ] Send **Henderson** the contract today"
    item = library.Item("m", "meeting", "Meeting", "Meeting", note, datetime.now())
    assert library.snippet(item, "henderson") == (
        "Meeting Action items Send Henderson the contract today"
    )
    text = "word " * 60 + "Henderson end"
    long_item = library.Item("x", "file", "File", "t", text, datetime.now())
    piece = library.snippet(long_item, "henderson", width=40)
    assert piece.startswith("...word") and "Henderson" in piece
