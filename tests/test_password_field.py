"""core/password_field.py talks to real Windows APIs; these tests only pin
down its promises to the caller: it always answers with a bool, never
raises, and never waits much longer than its timeout."""

import time

from core import password_field


def test_answers_with_a_bool_quickly():
    start = time.monotonic()
    result = password_field.focused_is_password(timeout=0.5)
    assert isinstance(result, bool)
    assert time.monotonic() - start < 2.0


def test_a_failing_check_counts_as_not_password(monkeypatch):
    def boom():
        raise OSError("no desktop")

    monkeypatch.setattr(password_field, "_foreground_is_this_process", lambda: False)
    monkeypatch.setattr(password_field, "_win32_focus_is_password", boom)
    monkeypatch.setattr(password_field, "_worker", None)
    monkeypatch.setattr(password_field, "_UiaWorker", lambda: (_ for _ in ()).throw(OSError()))
    assert password_field.focused_is_password() is False


def test_win32_password_edit_short_circuits(monkeypatch):
    monkeypatch.setattr(password_field, "_foreground_is_this_process", lambda: False)
    monkeypatch.setattr(password_field, "_win32_focus_is_password", lambda: True)
    assert password_field.focused_is_password() is True


def test_own_window_is_never_asked_about(monkeypatch):
    monkeypatch.setattr(password_field, "_foreground_is_this_process", lambda: True)
    monkeypatch.setattr(password_field, "_win32_focus_is_password", lambda: True)
    assert password_field.focused_is_password() is False


def test_busy_worker_does_not_queue_another_question():
    worker = password_field._UiaWorker.__new__(password_field._UiaWorker)
    import threading

    worker._busy = threading.Event()
    worker._busy.set()
    start = time.monotonic()
    assert worker.ask(timeout=5.0) is False
    assert time.monotonic() - start < 0.1
