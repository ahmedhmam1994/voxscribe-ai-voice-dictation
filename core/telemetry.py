"""Anonymous usage ping -- sends a single "app_launched" event to PostHog on
startup so we have real numbers on how many people actually run VoxScribe,
not just how many downloaded the installer.

Deliberately narrow: no audio, no transcripts, no text the user ever typed
or dictated, and no personally identifying information. The only identifier
sent is a random UUID generated once on first launch and stored locally
(QSettings) -- it isn't tied to a name, email, account, or hardware ID, and
nothing about it lets PostHog or us map an event back to a specific person.
See docs/privacy.html for the corresponding disclosure.

Never let telemetry affect the app itself: any failure here (no internet,
PostHog unreachable, whatever) is swallowed silently so it can't so much as
delay startup, let alone crash it.
"""

from __future__ import annotations

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


def send_app_launched() -> None:
    try:
        import posthog

        posthog.project_api_key = _POSTHOG_PROJECT_API_KEY
        posthog.host = _POSTHOG_HOST
        posthog.capture(
            "app_launched",
            distinct_id=_anonymous_id(),
            properties={
                "app_version": __version__,
                "os": platform.system(),
                "os_version": platform.release(),
            },
        )
    except Exception:
        # Telemetry must never take the app down with it.
        pass
