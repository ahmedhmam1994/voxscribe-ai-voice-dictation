"""Dictation modes: ready-made bundles of the per-app options (see
core/app_profiles.py), so the same hotkey writes the way each kind of app
expects.

- Chat: cleanup and smart formatting, and no full stop at the end of a
  one-sentence message, the way people type in chats.
- Email: cleanup, spoken punctuation and smart formatting, full sentences.
- Code: code dictation (Pro), no cleanup, no smart formatting.
- Notes: cleanup and spoken punctuation, nothing rewritten.

Free: pick one mode for everything. Pro: modes switch by themselves with the
focused app (AUTO_MODES below), and a per-app profile line can pick a mode
with `mode=chat` and still override single options. Everything is decided
from the program's file name only; VoxScribe never reads the screen.
"""

from __future__ import annotations

DEFAULT_MODE = "default"

MODES: dict[str, dict[str, object]] = {
    "default": {},
    "chat": {"cleanup": True, "voice_commands": True, "smart": True, "period": False},
    "email": {"cleanup": True, "voice_commands": True, "smart": True, "period": True},
    "code": {"code": True, "cleanup": False, "smart": False},
    "notes": {"cleanup": True, "voice_commands": True, "smart": False, "period": True},
}

MODE_LABELS = {
    "default": "Default (your settings as they are)",
    "chat": "Chat",
    "email": "Email",
    "code": "Code (Pro)",
    "notes": "Notes",
}

PRO_MODES = {"code"}

# Program file name -> mode, used when automatic switching is on (Pro).
# Browsers are left out on purpose: which site is open would need reading
# the screen, which VoxScribe never does.
AUTO_MODES: dict[str, str] = {
    # Chat
    "slack.exe": "chat",
    "discord.exe": "chat",
    "whatsapp.exe": "chat",
    "whatsapp.root.exe": "chat",
    "telegram.exe": "chat",
    "teams.exe": "chat",
    "ms-teams.exe": "chat",
    "signal.exe": "chat",
    "messenger.exe": "chat",
    "skype.exe": "chat",
    "zoom.exe": "chat",
    # Email
    "outlook.exe": "email",
    "olk.exe": "email",
    "thunderbird.exe": "email",
    "mailspring.exe": "email",
    "hxoutlook.exe": "email",
    # Code
    "code.exe": "code",
    "cursor.exe": "code",
    "windsurf.exe": "code",
    "devenv.exe": "code",
    "pycharm64.exe": "code",
    "idea64.exe": "code",
    "webstorm64.exe": "code",
    "rider64.exe": "code",
    "clion64.exe": "code",
    "goland64.exe": "code",
    "sublime_text.exe": "code",
    "windowsterminal.exe": "code",
    "wt.exe": "code",
    "powershell.exe": "code",
    "pwsh.exe": "code",
    "cmd.exe": "code",
    "notepad++.exe": "code",
    # Notes
    "winword.exe": "notes",
    "notion.exe": "notes",
    "obsidian.exe": "notes",
    "onenote.exe": "notes",
    "evernote.exe": "notes",
    "notepad.exe": "notes",
    "wordpad.exe": "notes",
    "logseq.exe": "notes",
}


def mode_for_app(
    process_name: str | None,
    profile: dict[str, object],
    global_mode: str,
    auto_switch: bool,
    is_pro: bool,
) -> str:
    """Which mode applies in this program."""
    mode = global_mode if global_mode in MODES else DEFAULT_MODE
    if is_pro:
        app = (process_name or "").lower()
        if auto_switch and app in AUTO_MODES:
            mode = AUTO_MODES[app]
        picked = profile.get("mode")
        if isinstance(picked, str) and picked in MODES:
            mode = picked
    if mode in PRO_MODES and not is_pro:
        mode = DEFAULT_MODE
    return mode


def effective_options(
    process_name: str | None,
    profile: dict[str, object],
    global_mode: str,
    auto_switch: bool,
    is_pro: bool,
) -> tuple[str, dict[str, object]]:
    """(mode, options) for a dictation in this program: the mode's options,
    then the per-app profile's own options on top (Pro only)."""
    mode = mode_for_app(process_name, profile, global_mode, auto_switch, is_pro)
    options = dict(MODES[mode])
    if is_pro:
        options.update({k: v for k, v in profile.items() if k != "mode"})
    return mode, options


def drop_final_period(text: str) -> str:
    """"See you at 5." -> "See you at 5", but only for a single sentence:
    a message with several sentences keeps its last full stop, and "etc." or
    "..." are left alone."""
    stripped = text.rstrip()
    if not stripped.endswith(".") or stripped.endswith(".."):
        return text
    body = stripped[:-1]
    if any(mark in body for mark in (". ", "! ", "? ", "\n")):
        return text
    last_word = body.rsplit(" ", 1)[-1].lower()
    if last_word in {"etc", "e.g", "i.e", "vs", "inc", "ltd", "jr", "sr", "dr", "mr", "mrs", "ms"}:
        return text
    return body + text[len(stripped):]
