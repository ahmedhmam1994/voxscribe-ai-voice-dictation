"""Tests for core/updater.py's version-comparison logic (the part that
doesn't require a real network call to GitHub)."""

from core.updater import _parse_version, is_newer


def test_parse_version_simple():
    assert _parse_version("1.3") == (1, 3)
    assert _parse_version("v1.3") == (1, 3)
    assert _parse_version("V1.3") == (1, 3)


def test_parse_version_three_part():
    assert _parse_version("1.3.1") == (1, 3, 1)


def test_parse_version_stops_at_non_numeric_suffix():
    assert _parse_version("1.3-beta") == (1, 3)
    assert _parse_version("1.3.0-rc1") == (1, 3, 0)


def test_parse_version_garbage_falls_back():
    assert _parse_version("") == (0,)
    assert _parse_version("vNext") == (0,)


def test_is_newer_true_for_bumped_version():
    assert is_newer("v1.4", "1.3") is True
    assert is_newer("v2.0", "1.9") is True


def test_is_newer_false_for_same_version():
    assert is_newer("v1.3", "1.3") is False


def test_is_newer_false_for_older_version():
    assert is_newer("v1.2", "1.3") is False


def test_is_newer_handles_patch_versions():
    assert is_newer("1.3.1", "1.3.0") is True
    assert is_newer("1.3.0", "1.3.1") is False


class _FakeResp:
    def __init__(self, chunks, content_length):
        self._chunks = list(chunks)
        self.headers = {} if content_length is None else {"Content-Length": str(content_length)}

    def read(self, _n=-1):
        return self._chunks.pop(0) if self._chunks else b""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _run_download(monkeypatch, tmp_path, resp):
    import urllib.request
    from pathlib import Path

    from core.updater import UpdateDownloadThread

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: resp)
    thread = UpdateDownloadThread("https://example.invalid/x.exe", "Setup.exe")
    results = []
    thread.done.connect(lambda p: results.append(("done", p)))
    thread.failed.connect(lambda m: results.append(("failed", m)))
    thread.run()
    return results, tmp_path / "Downloads" / "Setup.exe"


def test_complete_download_is_renamed(monkeypatch, tmp_path):
    results, dest = _run_download(monkeypatch, tmp_path, _FakeResp([b"abc", b"def"], 6))
    assert results[0][0] == "done"
    assert dest.read_bytes() == b"abcdef"


def test_truncated_download_fails_and_leaves_no_installer(monkeypatch, tmp_path):
    results, dest = _run_download(monkeypatch, tmp_path, _FakeResp([b"abc"], 1000))
    assert results[0][0] == "failed"
    assert not dest.exists()
    assert not dest.with_name(dest.name + ".part").exists()


def test_incomplete_read_emits_failed(monkeypatch, tmp_path):
    import http.client

    class _Dropping(_FakeResp):
        def read(self, _n=-1):
            raise http.client.IncompleteRead(b"abc", 10)

    results, dest = _run_download(monkeypatch, tmp_path, _Dropping([], 13))
    assert results[0][0] == "failed"
    assert not dest.exists()


def test_download_without_content_length_still_succeeds(monkeypatch, tmp_path):
    results, dest = _run_download(monkeypatch, tmp_path, _FakeResp([b"xyz"], None))
    assert results[0][0] == "done"
    assert dest.read_bytes() == b"xyz"
