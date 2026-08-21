"""Tests for core/crash_reporter.py's local-only crash logging."""

import sys

import core.crash_reporter as crash_reporter


def test_install_writes_local_log_and_still_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(crash_reporter, "LOG_DIR", tmp_path)

    original_hook = sys.excepthook
    seen: list[BaseException] = []
    sys.excepthook = lambda exc_type, exc_value, exc_tb: seen.append(exc_value)
    try:
        crash_reporter.install()
        try:
            raise RuntimeError("boom")
        except RuntimeError:
            sys.excepthook(*sys.exc_info())
    finally:
        sys.excepthook = original_hook

    assert len(seen) == 1
    assert str(seen[0]) == "boom"

    logs = list(tmp_path.glob("crash_*.log"))
    assert len(logs) == 1
    content = logs[0].read_text(encoding="utf-8")
    assert "VoxScribe" in content
    assert "RuntimeError" in content
    assert "boom" in content


def test_write_crash_log_survives_unwritable_dir(tmp_path, monkeypatch):
    # Point LOG_DIR at a path that can't be created (a file, not a
    # directory) to confirm a logging failure doesn't raise on its own.
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory")
    monkeypatch.setattr(crash_reporter, "LOG_DIR", blocked / "logs")

    try:
        raise ValueError("secondary failure")
    except ValueError:
        exc_info = sys.exc_info()

    crash_reporter._write_crash_log(*exc_info)  # should not raise
