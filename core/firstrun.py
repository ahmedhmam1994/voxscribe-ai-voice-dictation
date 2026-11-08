"""First-run funnel: where new installs stop before their first dictation.

Every step is reported as a fixed event name plus, for failures, a short fixed
code ("network", "denied", ...). Never an error message, a file path, a device
name, audio or text. The classifiers here turn raw exceptions into those codes
so nothing free-form can leave the machine. Sending goes through
core/telemetry.py, so the same random id and the same Settings switch apply.

The last step reached is also kept locally, so "Copy diagnostics" in Settings
can show a stuck user (and me) where they stopped. That part never leaves the
machine unless the user pastes it somewhere.
"""

from __future__ import annotations

import platform
import sys
import time

from app.version import __version__
from core import telemetry

MODEL_CODES = ("network", "disk", "blocked", "other")
MIC_CODES = ("denied", "no_device", "busy", "other")
HOTKEY_CODES = ("blocked", "conflict", "other")
TYPE_CODES = ("password_field", "no_focus", "error")


def classify_model_error(message: str) -> str:
    text = (message or "").lower()
    if any(k in text for k in ("no space", "disk full", "not enough space", "errno 28")):
        return "disk"
    if any(k in text for k in ("permission", "access is denied", "antivirus", "quarantin")):
        return "blocked"
    network_words = (
        "connection", "timed out", "timeout", "network", "resolve", "ssl", "offline", "proxy",
    )
    if any(k in text for k in network_words):
        return "network"
    return "other"


def classify_mic_error(message: str) -> str:
    text = (message or "").lower()
    if any(k in text for k in ("permission", "access is denied", "privacy", "not allowed")):
        return "denied"
    missing = ("no default", "no device", "not found", "invalid device", "no input")
    if any(k in text for k in missing):
        return "no_device"
    if any(k in text for k in ("busy", "in use", "exclusive", "already")):
        return "busy"
    return "other"


def classify_hotkey_error(message: str) -> str:
    text = (message or "").lower()
    if any(k in text for k in ("permission", "access", "privilege", "administrator")):
        return "blocked"
    if any(k in text for k in ("already", "conflict", "in use", "registered")):
        return "conflict"
    return "other"


def classify_activation(ok: bool, message: str) -> str:
    """activated, bad_key, device_limit, network or other, from the activation reply."""
    if ok:
        return "activated"
    text = (message or "").lower()
    if any(k in text for k in ("couldn't reach", "timed out", "urlopen", "network", "resolve")):
        return "network"
    if any(k in text for k in ("already", "another", "limit", "devices", "two")):
        return "device_limit"
    if any(k in text for k in ("isn't valid", "invalid", "typos", "not found", "unknown key")):
        return "bad_key"
    return "other"


def seconds_bucket(seconds: float) -> str:
    """A range, not the exact time: under_2s, 2_5s, 5_15s or over_15s."""
    if seconds < 2:
        return "under_2s"
    if seconds < 5:
        return "2_5s"
    if seconds < 15:
        return "5_15s"
    return "over_15s"


def mic_kind(device_name: str | None) -> str:
    """Bluetooth, usb, built_in or other, from the device name. The name itself is never sent."""
    name = (device_name or "").lower()
    if any(k in name for k in ("bluetooth", "hands-free", "airpods", "buds")):
        return "bluetooth"
    if "usb" in name:
        return "usb"
    if any(k in name for k in ("realtek", "internal", "built-in", "array", "laptop")):
        return "built_in"
    return "other"


def _context(**extra: str) -> dict[str, str]:
    from core import settings as app_settings

    props = {
        "build": "exe" if getattr(sys, "frozen", False) else "source",
        "gpu": "on" if app_settings.get_gpu_acceleration_enabled() else "off",
    }
    props.update({k: v for k, v in extra.items() if v})
    return props


def _note(step: str, code: str = "") -> None:
    """Remembers the last step locally for the diagnostics text."""
    try:
        store = telemetry._settings()
        store.setValue("firstrun_last_step", step)
        store.setValue("firstrun_last_code", code)
        store.setValue("firstrun_last_at", int(time.time()))
    except Exception:
        pass


def step(event: str, *, code: str = "", once: bool = False, **extra: str) -> None:
    """Records the step locally and sends it: once per install, or at most once a day."""
    _note(event, code)
    props = _context(**extra)
    if code:
        props["code"] = code
    if once:
        telemetry.send_once(event, **props)
    else:
        telemetry.send_daily(event, **props)


FEATURES = (
    "snippets", "try_harder", "file_import", "batch_import", "meeting", "dictation_mode",
    "link_import", "summary", "learned_word", "voice_profile",
)


def feature(name: str) -> None:
    """The first time each feature is used, once per install. Only the fixed name is sent."""
    if name in FEATURES:
        telemetry.send_once_keyed(name, "feature_used", feature=name)


def diagnostics_text(extra_lines: list[str] | None = None) -> str:
    """A short plain-text report the user can paste into a bug report or a reply."""
    try:
        store = telemetry._settings()
        last_step = str(store.value("firstrun_last_step", "") or "none yet")
        last_code = str(store.value("firstrun_last_code", "") or "")
        last_at = int(store.value("firstrun_last_at", 0) or 0)
    except Exception:
        last_step, last_code, last_at = "unknown", "", 0
    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(last_at)) if last_at else "never"
    lines = [
        f"VoxScribe {__version__} ({'exe' if getattr(sys, 'frozen', False) else 'source'})",
        f"Windows {platform.release()} {platform.version()}",
        f"Last step: {last_step}" + (f" ({last_code})" if last_code else "") + f" at {when}",
    ]
    lines.extend(extra_lines or [])
    return "\n".join(lines)
