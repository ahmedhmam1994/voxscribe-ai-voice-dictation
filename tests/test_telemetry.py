"""Tests for core/telemetry.py's dictation events. The PostHog send is replaced
with a recorder and settings are redirected to a throwaway ini file, so no test
reaches the network or the real registry key."""

import datetime

from PySide6.QtCore import QSettings

import core.settings as app_settings
import core.telemetry as telemetry


def _isolate(monkeypatch, tmp_path, *, enabled=True):
    ini_path = str(tmp_path / "settings.ini")
    monkeypatch.setattr(
        telemetry, "_settings", lambda: QSettings(ini_path, QSettings.Format.IniFormat)
    )
    monkeypatch.setattr(app_settings, "get_telemetry_enabled", lambda: enabled)
    sent: list[str] = []
    monkeypatch.setattr(telemetry, "_capture", lambda event: sent.append(event))
    return sent


def test_the_first_dictation_sends_both_events():
    assert telemetry.events_for_dictation(False, None, "2026-10-22") == [
        "first_dictation",
        "dictated_today",
    ]


def test_a_later_dictation_on_a_new_day_sends_only_the_daily_event():
    assert telemetry.events_for_dictation(True, "2026-10-21", "2026-10-22") == ["dictated_today"]


def test_more_dictations_the_same_day_send_nothing():
    assert telemetry.events_for_dictation(True, "2026-10-22", "2026-10-22") == []


def test_the_events_go_out_once_even_after_many_dictations(monkeypatch, tmp_path):
    sent = _isolate(monkeypatch, tmp_path)

    telemetry.send_dictation_used()
    telemetry.send_dictation_used()
    telemetry.send_dictation_used()

    assert sent == ["first_dictation", "dictated_today"]


def test_a_new_day_sends_the_daily_event_again(monkeypatch, tmp_path):
    sent = _isolate(monkeypatch, tmp_path)
    telemetry.send_dictation_used()
    store = telemetry._settings()
    store.setValue(
        "telemetry_last_dictation_day",
        (datetime.date.today() - datetime.timedelta(days=1)).isoformat(),
    )
    store.sync()

    telemetry.send_dictation_used()

    assert sent == ["first_dictation", "dictated_today", "dictated_today"]


def test_nothing_is_sent_or_remembered_while_telemetry_is_off(monkeypatch, tmp_path):
    sent = _isolate(monkeypatch, tmp_path, enabled=False)

    telemetry.send_dictation_used()

    assert sent == []
    assert telemetry._settings().value("telemetry_first_dictation_sent", False) in (False, "false")


def test_turning_telemetry_on_later_starts_counting_then(monkeypatch, tmp_path):
    sent = _isolate(monkeypatch, tmp_path, enabled=False)
    telemetry.send_dictation_used()
    monkeypatch.setattr(app_settings, "get_telemetry_enabled", lambda: True)

    telemetry.send_dictation_used()

    assert sent == ["first_dictation", "dictated_today"]


def test_a_failure_never_escapes(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    def broken(event):
        raise RuntimeError("PostHog is down")

    monkeypatch.setattr(telemetry, "_capture", broken)

    telemetry.send_dictation_used()  # must not raise
