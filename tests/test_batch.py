"""Tests for core/batch.py."""

from core import batch


def _touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    return str(path)


def test_collect_expands_folders_and_filters(tmp_path):
    a = _touch(tmp_path / "a.mp3")
    b = _touch(tmp_path / "sub" / "b.MP4")
    _touch(tmp_path / "notes.txt")
    assert batch.collect_media([str(tmp_path)]) == [a, b]


def test_collect_accepts_files_and_drops_duplicates(tmp_path):
    a = _touch(tmp_path / "a.wav")
    assert batch.collect_media([a, a, str(tmp_path)]) == [a]


def test_collect_ignores_missing_and_non_media(tmp_path):
    assert batch.collect_media([str(tmp_path / "nope.mp3"), _touch(tmp_path / "x.doc")]) == []


def test_split_done_skips_files_with_an_srt(tmp_path):
    a = _touch(tmp_path / "a.mp3")
    b = _touch(tmp_path / "b.mp3")
    _touch(tmp_path / "a.srt")
    assert batch.split_done([a, b]) == ([b], [a])


def test_overall_percent():
    assert batch.overall_percent(0, 4, 50) == 12
    assert batch.overall_percent(3, 4, 100) == 100
    assert batch.overall_percent(1, 0, 10) == 0
    assert batch.overall_percent(1, 2, 500) == 100


def test_common_folder(tmp_path):
    a = _touch(tmp_path / "x" / "a.mp3")
    b = _touch(tmp_path / "y" / "b.mp3")
    assert batch.common_folder([a, b]) == str(tmp_path)
    assert batch.common_folder([]) is None


def test_summary_text():
    assert (
        batch.format_summary(12, 10, 1, 1, 10, False)
        == "Batch done: 10 of 12 files transcribed, 10 .srt saved, 1 failed, "
        "1 skipped (already had an .srt)."
    )
    assert batch.format_summary(5, 2, 0, 0, 0, True) == "Batch stopped: 2 of 5 files transcribed."
