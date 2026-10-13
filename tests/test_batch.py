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


def test_unused_base_keeps_the_name_when_free(tmp_path):
    src = _touch(tmp_path / "talk.mp3")
    assert batch.unused_base(src, [".srt"]) == tmp_path / "talk"


def test_unused_base_never_replaces_an_existing_srt(tmp_path):
    src = _touch(tmp_path / "talk.mp3")
    _touch(tmp_path / "talk.srt")
    assert batch.unused_base(src, [".srt"]) == tmp_path / "talk (2)"
    _touch(tmp_path / "talk (2).srt")
    assert batch.unused_base(src, [".srt"]) == tmp_path / "talk (3)"


def test_unused_base_keeps_all_outputs_together(tmp_path):
    src = _touch(tmp_path / "talk.mp3")
    _touch(tmp_path / "talk.docx")
    assert batch.unused_base(src, [".srt", ".docx"]) == tmp_path / "talk (2)"


def test_unused_base_with_dots_in_the_name(tmp_path):
    src = _touch(tmp_path / "my.talk.v2.mp3")
    _touch(tmp_path / "my.talk.v2.srt")
    assert batch.unused_base(src, [".srt"]) == tmp_path / "my.talk.v2 (2)"


def test_report_lists_failures_first_and_where_srt_went(tmp_path):
    folder = str(tmp_path)
    results = [
        {"path": str(tmp_path / "a.mp3"), "status": "done", "srt": str(tmp_path / "a.srt")},
        {"path": str(tmp_path / "b.mp3"), "status": "failed", "error": "corrupt file"},
        {"path": str(tmp_path / "sub" / "c.mp3"), "status": "skipped"},
        {"path": str(tmp_path / "d.mp3"), "status": "not run"},
    ]
    lines = batch.format_report(results, folder)
    assert lines[0] == "  failed: b.mp3 (corrupt file)"
    assert lines[1].startswith("  not run: d.mp3")
    assert "  done: a.mp3 -> a.srt" in lines
    assert any("skipped" in line and "c.mp3" in line for line in lines)


def test_to_retry_is_failed_and_unstarted_only(tmp_path):
    results = [
        {"path": "a", "status": "done"},
        {"path": "b", "status": "failed"},
        {"path": "c", "status": "not run"},
        {"path": "d", "status": "skipped"},
    ]
    assert batch.to_retry(results) == ["b", "c"]


def test_failure_reason_drops_the_long_path():
    err = r"[Errno 1094995529] Invalid data found when processing input: 'C:\Users\x\media\bad.mp3'"
    lines = batch.format_report([{"path": "bad.mp3", "status": "failed", "error": err}], None)
    assert lines == ["  failed: bad.mp3 (Invalid data found when processing input)"]
