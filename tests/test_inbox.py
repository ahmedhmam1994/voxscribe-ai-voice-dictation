from datetime import datetime

from core import inbox

NOW = datetime(2026, 10, 28, 14, 32)


def test_first_note_creates_the_file_with_title_day_and_line(tmp_path):
    path = tmp_path / "vault" / "VoxScribe Inbox.md"
    assert inbox.append_note(path, "Call the clinic", NOW)
    assert path.read_text(encoding="utf-8") == (
        "# VoxScribe Inbox\n\n## 2026-10-28\n- 14:32 Call the clinic\n"
    )


def test_same_day_adds_a_line_without_a_new_heading(tmp_path):
    path = tmp_path / "inbox.md"
    inbox.append_note(path, "one", NOW)
    inbox.append_note(path, "two", datetime(2026, 10, 28, 15, 5))
    text = path.read_text(encoding="utf-8")
    assert text.count("## 2026-10-28") == 1
    assert text.endswith("- 14:32 one\n- 15:05 two\n")


def test_next_day_gets_a_new_heading(tmp_path):
    path = tmp_path / "inbox.md"
    inbox.append_note(path, "one", NOW)
    inbox.append_note(path, "two", datetime(2026, 10, 29, 9, 0))
    assert path.read_text(encoding="utf-8").endswith("- 14:32 one\n## 2026-10-29\n- 09:00 two\n")


def test_text_is_kept_on_one_line_and_blank_text_is_skipped(tmp_path):
    path = tmp_path / "inbox.md"
    assert not inbox.append_note(path, "  \n ", NOW)
    assert not path.exists()
    inbox.append_note(path, "a\nb   c", NOW)
    assert "- 14:32 a b c\n" in path.read_text(encoding="utf-8")


def test_existing_notes_file_without_final_newline_is_continued(tmp_path):
    path = tmp_path / "inbox.md"
    path.write_text("# My own title", encoding="utf-8")
    inbox.append_note(path, "idea", NOW)
    assert path.read_text(encoding="utf-8") == "# My own title\n## 2026-10-28\n- 14:32 idea\n"


def test_non_ascii_text(tmp_path):
    path = tmp_path / "inbox.md"
    inbox.append_note(path, "اجتماع مهم غدا", NOW)
    assert "اجتماع مهم غدا" in path.read_text(encoding="utf-8")


def test_default_path_is_in_documents():
    assert inbox.default_path().name == "VoxScribe Inbox.md"
    assert inbox.default_path().parent.name == "Documents"
