"""Anonymous usage pings sent to PostHog, so we have real numbers on how many
people actually use VoxScribe, not just how many downloaded the installer.

Narrow events, all of them listed in docs/privacy.html:
- "app_launched", on every start.
- "first_dictation", once per install, the first time a dictation is typed.
- "dictated_today", at most once a day, when a dictation is typed that day. It
  counts people who leave the app running in the tray for weeks, which the
  launch ping alone cannot see.
- The first-run funnel (core/firstrun.py): which step a new install reached
  and, for a failure, a fixed code such as "network" or "denied". Never an
  error message, a path, a device name, audio or text.

Deliberately narrow: no audio, no transcripts, no text the user ever typed
or dictated, no word counts, and no personally identifying information. The
only identifier sent is a random UUID generated once on first launch and
stored locally (QSettings) -- it isn't tied to a name, email, account, or
hardware ID, and nothing about it lets PostHog or us map an event back to a
specific person. All of them are switched off by the one telemetry setting.
See docs/privacy.html for the corresponding disclosure.

Never let telemetry affect the app itself: any failure here (no internet,
PostHog unreachable, whatever) is swallowed silently so it can't so much as
delay startup, let alone crash it.
"""

from __future__ import annotations

import datetime
import platform
import uuid

from PySide6.QtCore import QSettings

from app.version import __version__

# Project API key (safe to embed -- it can only send events, not read or
# manage the PostHog account; see .env's POSTHOG_PERSONAL_API_KEY comment
# for the key that must NOT end up here).
_POSTHOG_PROJECT_API_KEY = "phc_vkYFuUzTmMNT4bUffuMjiNSMnAqkQgPEp3vCHYrzFWoH"
_POSTHOG_HOST = "https://us.i.posthog.com"


def _settings() -> QSettings:
    return QSettings("VoxScribe", "VoxScribe")


def _anonymous_id() -> str:
    """A random id generated once and reused across launches, so PostHog can
    tell repeat launches from new installs without knowing who anyone is."""
    settings = _settings()
    existing = settings.value("telemetry_anonymous_id", "")
    if existing:
        return str(existing)
    new_id = str(uuid.uuid4())
    settings.setValue("telemetry_anonymous_id", new_id)
    return new_id


def _capture(event: str, **extra: str) -> None:
    """Sends one event if the user allows it. Never raises."""
    try:
        from core import settings as app_settings

        if not app_settings.get_telemetry_enabled():
            return

        import posthog

        posthog.project_api_key = _POSTHOG_PROJECT_API_KEY
        posthog.host = _POSTHOG_HOST
        posthog.capture(
            event,
            distinct_id=_anonymous_id(),
            properties={
                "app_version": __version__,
                "os": platform.system(),
                "os_version": platform.release(),
                **extra,
            },
        )
    except Exception:
        # Telemetry must never take the app down with it.
        pass


def send_app_launched() -> None:
    _capture("app_launched")


def events_for_dictation(first_sent: bool, last_day: str | None, today: str) -> list[str]:
    """Which events a typed dictation should send: the first-ever one, and the
    first of each day. Pure, so it can be tested without a settings store."""
    events: list[str] = []
    if not first_sent:
        events.append("first_dictation")
    if last_day != today:
        events.append("dictated_today")
    return events


def _as_bool(value: object) -> bool:
    if isinstance(value, str):
        return value.lower() == "true"
    return bool(value)


def send_dictation_used() -> None:
    """Call after a dictation was typed. Sends "first_dictation" once ever and
    "dictated_today" once a day. Nothing is marked as sent while the user has
    telemetry off, so turning it on later starts counting from the next dictation."""
    try:
        from core import settings as app_settings

        if not app_settings.get_telemetry_enabled():
            return

        store = _settings()
        first_sent = _as_bool(store.value("telemetry_first_dictation_sent", False))
        last_day = str(store.value("telemetry_last_dictation_day", "") or "") or None
        today = datetime.date.today().isoformat()
        events = events_for_dictation(first_sent, last_day, today)
        if not events:
            return

        # Marked before sending, so two dictations in a row send each event once.
        store.setValue("telemetry_first_dictation_sent", True)
        store.setValue("telemetry_last_dictation_day", today)
        for event in events:
            _capture(event)
    except Exception:
        pass


def level_for_peak(peak: float) -> str:
    """A coarse label for how loud a recording was, from its loudest sample (0 to 1)."""
    if peak < 0.01:
        return "silent"
    if peak < 0.05:
        return "quiet"
    return "normal"


def _send_marked(marker: str, event: str, props: dict[str, str], *, daily: bool) -> None:
    """Sends `event` once per install, or at most once a day. Nothing is marked as
    sent while telemetry is off. Never raises."""
    try:
        from core import settings as app_settings

        if not app_settings.get_telemetry_enabled():
            return
        store = _settings()
        if daily:
            today = datetime.date.today().isoformat()
            if str(store.value(marker, "") or "") == today:
                return
            store.setValue(marker, today)
        else:
            if _as_bool(store.value(marker, False)):
                return
            store.setValue(marker, True)
        _capture(event, **props)
    except Exception:
        pass


def send_once(event: str, **props: str) -> None:
    """Sends `event` once per install."""
    _send_marked(f"telemetry_once_{event}", event, props, daily=False)


def send_once_keyed(key: str, event: str, **props: str) -> None:
    """Sends `event` once per install for each distinct `key`."""
    _send_marked(f"telemetry_once_{event}_{key}", event, props, daily=False)


def send_daily(event: str, **props: str) -> None:
    """Sends `event` at most once a day."""
    _send_marked(f"telemetry_day_{event}", event, props, daily=True)
