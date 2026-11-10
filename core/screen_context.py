"""Words from the window you are typing into, used as hints for the speech model.

Dictating into "Q3 forecast.xlsx - Excel" or "main_window.py - VoxScribe -
Visual Studio Code" is far more likely to mention those names than a random
sentence is. The window title is read on this PC only, and the words go to the
local model as a hint. Nothing is stored and nothing leaves the computer.
"""

from __future__ import annotations

import ctypes
import re

# Words that name the program or the situation rather than the work.
_NOISE = {
    "untitled", "new", "tab", "page", "window", "document", "file", "edit", "view", "home",
    "inbox", "search", "settings", "welcome", "chrome", "google", "firefox", "edge", "microsoft",
    "mozilla", "opera", "brave", "visual", "studio", "code", "notepad", "word", "excel",
    "powerpoint", "outlook", "teams", "slack", "discord", "whatsapp", "telegram", "explorer",
    "the", "and", "for", "with", "from", "your", "you", "not", "are", "was", "this", "that",
    "chat", "mail", "email", "docs", "sheets", "slides", "drive", "calendar", "profile",
    "dashboard", "login", "sign", "log", "web", "app", "browser", "private", "incognito",
}  # fmt: skip
_SEPARATORS = re.compile(r"\s[-–—|·•]\s")
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[._][A-Za-z0-9]+)*")
_EXTENSION = re.compile(r"\.(py|js|ts|tsx|md|txt|docx?|xlsx?|pptx?|pdf|html?|css|json|csv)$")
MAX_TERMS = 8


def window_title(hwnd: int | None = None) -> str:
    """The title text of a window (the focused one by default), or ''."""
    user32 = ctypes.windll.user32
    handle = hwnd or user32.GetForegroundWindow()
    if not handle:
        return ""
    length = user32.GetWindowTextLengthW(handle)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(handle, buf, length + 1)
    return buf.value


def terms_from_title(title: str, own_names: tuple[str, ...] = ("voxscribe",)) -> list[str]:
    """Names worth hinting from a window title, most distinctive first.

    The last part of a title is usually the program ("... - Google Chrome"),
    so it is dropped; file extensions are cut; common program and page words
    are skipped; plain lower-case words are not names, so they are left out."""
    parts = [p for p in _SEPARATORS.split(title.strip()) if p.strip()]
    if len(parts) > 1:
        parts = parts[:-1]
    found: list[tuple[int, str]] = []
    seen: set[str] = set()
    for part in parts:
        for raw in _WORD.findall(part):
            word = _EXTENSION.sub("", raw).strip("._")
            key = word.lower()
            if len(word) < 3 or key in _NOISE or key in seen or key in own_names:
                continue
            seen.add(key)
            if any(c.isdigit() for c in word) or re.search(r"[a-z][A-Z]|[._]", word):
                rank = 0  # mixed case, digits or dots: an identifier or file name
            elif word[0].isupper():
                rank = 1  # a capitalised name
            else:
                continue
            found.append((rank, word))
    found.sort(key=lambda row: row[0])  # stable: title order within a rank
    return [word for _rank, word in found][:MAX_TERMS]
