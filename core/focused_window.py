"""Detects which process owns the currently focused window.

Used by the app-exclusion setting (Settings -> Disabled Apps) to check what
has focus right before a recording starts, so VoxScribe never types into a
password manager or similar app that was explicitly excluded. Pure ctypes
against user32/kernel32 -- no pywin32 dependency, matching the rest of this
project's preference for stdlib-only where practical (see core/updater.py's
own docstring on why it uses urllib instead of requests).
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def foreground_process_name() -> str | None:
    """The executable filename (e.g. "keepass.exe", lowercased) of whatever
    window currently has OS focus, or None if it can't be determined."""
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return None

    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return None

    handle = _kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return None
    try:
        buf = ctypes.create_unicode_buffer(260)
        size = wintypes.DWORD(260)
        if not _kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return None
        path = buf.value
        return path.rsplit("\\", 1)[-1].lower() if path else None
    finally:
        _kernel32.CloseHandle(handle)
