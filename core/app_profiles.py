"""Per-app profiles -- a Pro feature (see core/license.py). A profile changes a
few dictation settings for one program, so the same hotkey does the right
thing in each: code dictation in the editor, no cleanup in the terminal, a
different language in a chat app.

Matched by the focused program's executable name (the same name the disabled
apps list uses, see core/focused_window.py). An option a profile does not set
falls back to the normal setting.

Written in Settings as one line per app, in the same style as word
replacements and snippets:

    code.exe => code=on, cleanup=off, language=en
    slack.exe => mode=notes, smart=off

`mode` picks one of the dictation modes (core/modes.py); the other options
then override single settings of that mode. `packs` picks the term packs for
that app (core/term_packs.py): `packs=medical+legal`, or `packs=off` for none.
"""

from __future__ import annotations

import json

from PySide6.QtCore import QSettings

from core.modes import MODES
from core.term_packs import BUILTIN_PACKS

# option name -> kind. "language" takes a language code or "auto", "mode" a mode
# name from core/modes.py; the rest are on/off.
OPTIONS = {
    "mode": "mode",
    "language": "language",
    "cleanup": "flag",
    "voice_commands": "flag",
    "code": "flag",
    "smart": "flag",
    "period": "flag",
    "packs": "packs",
}
_ON = {"on", "true", "yes", "1"}
_OFF = {"off", "false", "no", "0"}


def _settings() -> QSettings:
    return QSettings("VoxScribe", "VoxScribe")


def parse_lines(text: str) -> dict[str, dict[str, object]]:
    """`name.exe => option=value, ...` lines -> {name.exe: {option: value}}.
    Unknown options, bad values and empty profiles are dropped."""
    profiles: dict[str, dict[str, object]] = {}
    for line in text.splitlines():
        app, arrow, options = line.partition("=>")
        app = app.strip().lower()
        if not arrow or not app:
            continue
        chosen: dict[str, object] = {}
        for part in options.split(","):
            name, equals, value = part.partition("=")
            name, value = name.strip().lower(), value.strip().lower()
            kind = OPTIONS.get(name)
            if not equals or kind is None:
                continue
            if kind == "language" and value:
                chosen[name] = None if value == "auto" else value
            elif kind == "mode" and value in MODES:
                chosen[name] = value
            elif kind == "flag" and value in _ON | _OFF:
                chosen[name] = value in _ON
            elif kind == "packs":
                packs = _parse_packs(value)
                if packs is not None:
                    chosen[name] = packs
        if chosen:
            profiles[app] = chosen
    return profiles


def _parse_packs(value: str) -> list[str] | None:
    """"medical+legal" -> ["medical", "legal"]; "off" -> []; anything with an
    unknown pack name -> None (the option is dropped)."""
    if value in _OFF or value == "none":
        return []
    known = {pack_id for pack_id, _label in BUILTIN_PACKS}
    names = [part.strip() for part in value.replace(",", "+").split("+") if part.strip()]
    if not names or any(name not in known for name in names):
        return None
    return list(dict.fromkeys(names))


def format_lines(profiles: dict[str, dict[str, object]]) -> str:
    lines = []
    for app, options in profiles.items():
        parts = []
        for name, value in options.items():
            if OPTIONS.get(name) == "language":
                parts.append(f"{name}={value or 'auto'}")
            elif OPTIONS.get(name) == "mode":
                parts.append(f"{name}={value}")
            elif OPTIONS.get(name) == "packs":
                parts.append(f"{name}={'+'.join(value) if value else 'off'}")
            else:
                parts.append(f"{name}={'on' if value else 'off'}")
        lines.append(f"{app} => {', '.join(parts)}")
    return "\n".join(lines)


def get_profiles() -> dict[str, dict[str, object]]:
    raw = _settings().value("app_profiles", "")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def set_profiles(profiles: dict[str, dict[str, object]]) -> None:
    _settings().setValue("app_profiles", json.dumps(profiles))


def profile_for(process_name: str | None) -> dict[str, object]:
    """The options set for this program, or an empty dict when it has none."""
    if not process_name:
        return {}
    return get_profiles().get(process_name.lower(), {})
