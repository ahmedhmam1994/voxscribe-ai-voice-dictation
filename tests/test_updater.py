"""Tests for core/updater.py's version-comparison logic (the part that
doesn't require a real network call to GitHub)."""

import http.client
import urllib.request
from pathlib import Path

from core.updater import UpdateDownloadThread, _parse_version, is_newer


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


class _DroppedResponse:
    """A response whose connection dies partway through the body."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, _size):
        raise http.client.IncompleteRead(b"partial")


def test_download_dropped_connection_reports_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _DroppedResponse())

    thread = UpdateDownloadThread("https://example.invalid/setup.exe", "setup.exe")
    failures: list[str] = []
    thread.failed.connect(failures.append)
    thread.done.connect(lambda path: failures.append("unexpected success"))
    thread.run()  # run() directly: no event loop needed, signals are direct here

    assert len(failures) == 1
    assert "unexpected" not in failures[0]
    assert not (tmp_path / "Downloads" / "setup.exe").exists()
    assert not (tmp_path / "Downloads" / "setup.exe.part").exists()
