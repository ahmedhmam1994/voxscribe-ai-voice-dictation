"""Dark and light looks for VoxScribe.

The app was drawn dark first, with its colours as hex strings in the style
sheets. Rather than duplicate every style sheet, light mode swaps each dark
colour for a light one at the moment a style sheet or colour is applied. The
choice is read once at start-up (Settings -> General -> Appearance, takes
effect after a restart): "dark" (the default, unchanged), "light", or "system"
to follow Windows' own app theme.

Rules for the table below: no light value may also appear as a dark key (it
would be swapped twice), and every dark colour the app uses is listed. A dark
colour that is missing simply stays as it is.
"""

from __future__ import annotations

import re
import winreg

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget

from core import settings as hotkey_settings

# dark colour -> light colour
_LIGHT: dict[str, str] = {
    # window and surfaces
    "#121319": "#f3f4f8",
    "#14151d": "#f6f7fa",
    "#0e0f14": "#eceef3",
    "#0d0e13": "#e9ebf1",
    "#14151c": "#f1f2f6",
    "#181a23": "#fafafc",
    "#1a1c26": "#fbfbfd",
    "#1b1d27": "#ffffff",
    "#1b1e28": "#fcfcfe",
    "#1d1f2a": "#f8f9fc",
    "#1f212c": "#f5f6fa",
    "#22242f": "#eaecf3",
    "#23252f": "#e8eaf1",
    "#242631": "#e4e7ee",
    "#262833": "#e2e5ed",
    # borders
    "#2a2d3a": "#dadde7",
    "#2b2e3b": "#d6dae5",
    "#2e3140": "#d3d7e2",
    "#3a3b4c": "#c8ccd9",
    "#3a3d4c": "#c6cad8",
    # text
    "#eceef4": "#1c1e29",
    "#f1f2f8": "#161821",
    "#8b8d9c": "#5a5e70",
    "#5c5e6c": "#7d8194",
    # accent green (darker so text and borders keep their contrast on white)
    "#3ecf8e": "#17895a",
    "#4ee0a0": "#35c786",
    "#34b57a": "#27a56e",
    "#2bb673": "#20a064",
    "#269e69": "#1b8758",
    "#1f8f5c": "#17794d",
    "#17754d": "#0f633f",
    "#2fae76": "#1f9a68",
    "#4aa06c": "#2d8a56",
    "#8eeab0": "#127a4e",
    "#5ce3a6": "#2bb57c",
    # accent tints that were dark green backgrounds
    "#1c2a25": "#e1f3ea",
    "#21392f": "#d4eddf",
    "#163a28": "#c9e8d7",
    "#2a4d3d": "#bfe3cf",
    "#2f7a52": "#3d9a6a",
    # status colours
    "#f0546b": "#d93a54",
    "#f0a54a": "#b8740f",
}

_PATTERN = re.compile("|".join(re.escape(k) for k in _LIGHT), re.IGNORECASE)

_light: bool | None = None


def _system_prefers_light() -> bool:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            return bool(winreg.QueryValueEx(key, "AppsUseLightTheme")[0])
    except OSError:
        return False


def is_light() -> bool:
    """True when the app should draw light. Read once, so every part of one
    run agrees even if Windows switches theme meanwhile."""
    global _light
    if _light is None:
        choice = hotkey_settings.get_appearance()
        _light = choice == "light" or (choice == "system" and _system_prefers_light())
    return _light


def hx(color: str) -> str:
    """One colour for the current look."""
    return _LIGHT.get(color.lower(), color) if is_light() else color


def t(css: str) -> str:
    """A style sheet (or any string holding hex colours) for the current look."""
    if not is_light():
        return css
    return _PATTERN.sub(lambda match: _LIGHT[match.group(0).lower()], css)


def qc(color: str) -> QColor:
    return QColor(hx(color))


def install() -> None:
    """Makes every widget's setStyleSheet apply the look, so the many places that
    style themselves need no change. A widget that must stay dark whatever the
    look (the floating pill) sets the property keepDark before styling itself."""
    if not is_light():
        return
    original = QWidget.setStyleSheet

    def themed(self: QWidget, css: str) -> None:
        original(self, css if self.property("keepDark") else t(css))

    QWidget.setStyleSheet = themed  # type: ignore[method-assign]
