"""Detects and re-targets which window owns OS focus.

`foreground_process_name()` is used by the app-exclusion setting (Settings
-> Disabled Apps) to check what has focus right before a recording starts,
so VoxScribe never types into a password manager or similar app that was
explicitly excluded.

`foreground_window_handle()` / `focus_window()` exist so the typed-output
path (see app/main_window.py's `_stop_recording`/`_type_into_focused_window`)
can remember which window the user was dictating into and refocus it before
typing, since transcription runs in the background and finishes after a
delay -- long enough for the user to have switched windows in the meantime,
which would otherwise send the text to the wrong app.

Pure ctypes against user32/kernel32 -- no pywin32 dependency, matching the
rest of this project's preference for stdlib-only where practical (see
core/updater.py's own docstring on why it uses urllib instead of requests).
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_SW_RESTORE = 9


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


def foreground_window_handle() -> int | None:
    """The HWND of whatever window currently has OS focus, or None."""
    hwnd = _user32.GetForegroundWindow()
    return hwnd if hwnd else None


def focus_window(hwnd: int) -> bool:
    """Best-effort attempt to restore OS focus to `hwnd`.

    Returns whether it apparently worked. `hwnd` may point to a window that
    was closed since it was captured (IsWindow catches that), or Windows may
    simply refuse the focus change -- SetForegroundWindow is restricted so an
    unrelated background process can't steal focus from whatever the user is
    actively doing, and that restriction applies here too since VoxScribe
    isn't the window the user is currently interacting with when this runs.
    There's no way to force it past that restriction without much more
    invasive tricks (e.g. attaching input queues to the target thread), which
    isn't worth the complexity for this: on failure, the caller just falls
    back to typing into whatever window is currently focused instead.
    """
    if not hwnd or not _user32.IsWindow(hwnd):
        return False
    if _user32.IsIconic(hwnd):
        _user32.ShowWindow(hwnd, _SW_RESTORE)
    return bool(_user32.SetForegroundWindow(hwnd))
