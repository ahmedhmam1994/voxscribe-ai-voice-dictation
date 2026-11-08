"""Reads the text of the box that has the keyboard focus, for learning your
words (core/learned_words.py): VoxScribe notes the box right after typing
into it and looks again a little later, so a word you fixed by hand can be
learned.

UI Automation's Value property of the focused element: plain text boxes in
browsers, classic Win32 edit boxes, WinUI/WPF text boxes. Rich editors that
do not offer a value (some web chat boxes, Word) give None, and nothing is
learned there. Password fields are never read.

The text stays in memory for the comparison only. It is never saved, logged
or sent anywhere. Same raw COM calls as core/password_field.py, on a
background thread of its own with a short timeout, so a hung app never
stalls VoxScribe.
"""

from __future__ import annotations

import ctypes
import queue
import threading
import time

from core.password_field import (
    _CHROMIUM_WAKE_SEC,
    _CLSID_CUIAUTOMATION,
    _ELEMENT_GET_CURRENT_CONTROL_TYPE,
    _ELEMENT_GET_CURRENT_PROPERTY_VALUE,
    _IID_IUIAUTOMATION,
    _IUIAUTOMATION_GET_FOCUSED_ELEMENT,
    _UIA_IS_PASSWORD_PROPERTY_ID,
    _UIA_PANE_CONTROL_TYPE_ID,
    _VARIANT,
    _VT_BOOL,
    _com_method,
    _foreground_is_this_process,
    _guid,
    _release,
)

_UIA_VALUE_VALUE_PROPERTY_ID = 30045
_VT_BSTR = 8
DEFAULT_TIMEOUT_SEC = 0.6
# A huge document is not worth comparing word by word on every check.
MAX_CHARS = 20000


def _property(element: ctypes.c_void_p, property_id: int) -> _VARIANT:
    value = _VARIANT()
    get_property = _com_method(
        element, _ELEMENT_GET_CURRENT_PROPERTY_VALUE, ctypes.c_int, ctypes.POINTER(_VARIANT)
    )
    get_property(element, property_id, ctypes.byref(value))
    return value


def _read_focused(automation: ctypes.c_void_p) -> tuple[str | None, bool]:
    """(the focused box's text or None, the focused element is a bare pane)."""
    element = ctypes.c_void_p()
    get_focused = _com_method(
        automation, _IUIAUTOMATION_GET_FOCUSED_ELEMENT, ctypes.POINTER(ctypes.c_void_p)
    )
    try:
        get_focused(automation, ctypes.byref(element))
    except OSError:
        return None, False
    if not element:
        return None, False
    oleaut32 = ctypes.oledll.oleaut32
    try:
        control_type = ctypes.c_int()
        get_type = _com_method(
            element, _ELEMENT_GET_CURRENT_CONTROL_TYPE, ctypes.POINTER(ctypes.c_int)
        )
        get_type(element, ctypes.byref(control_type))
        is_pane = control_type.value == _UIA_PANE_CONTROL_TYPE_ID
        secret = _property(element, _UIA_IS_PASSWORD_PROPERTY_ID)
        is_password = secret.vt == _VT_BOOL and (secret.value & 0xFFFF) != 0
        oleaut32.VariantClear(ctypes.byref(secret))
        if is_password:
            return None, False
        value = _property(element, _UIA_VALUE_VALUE_PROPERTY_ID)
        try:
            if value.vt != _VT_BSTR or not value.value:
                return None, is_pane
            text = ctypes.wstring_at(value.value)
        finally:
            oleaut32.VariantClear(ctypes.byref(value))
        return (text if len(text) <= MAX_CHARS else None), is_pane
    except OSError:
        return None, False
    finally:
        _release(element)


class _Reader:
    def __init__(self) -> None:
        self._requests: queue.Queue[tuple[threading.Event, list]] = queue.Queue()
        self._busy = threading.Event()
        threading.Thread(target=self._run, name="uia-text", daemon=True).start()

    def ask(self, timeout: float) -> str | None:
        if self._busy.is_set():
            return None
        done = threading.Event()
        answer: list = []
        self._requests.put((done, answer))
        if not done.wait(timeout):
            return None
        return answer[0] if answer else None

    def _run(self) -> None:
        ole32 = ctypes.oledll.ole32
        try:
            ole32.CoInitializeEx(None, 0)
        except OSError:
            pass
        automation = ctypes.c_void_p()
        try:
            clsid = _guid(_CLSID_CUIAUTOMATION)
            iid = _guid(_IID_IUIAUTOMATION)
            ole32.CoCreateInstance(
                ctypes.byref(clsid), None, 1, ctypes.byref(iid), ctypes.byref(automation)
            )
        except OSError:
            automation = ctypes.c_void_p()
        while True:
            done, answer = self._requests.get()
            self._busy.set()
            try:
                text = None
                if automation:
                    text, is_pane = _read_focused(automation)
                    if text is None and is_pane:
                        time.sleep(_CHROMIUM_WAKE_SEC)
                        text, _ = _read_focused(automation)
                answer.append(text)
            except Exception:  # noqa: BLE001
                answer.append(None)
            finally:
                self._busy.clear()
                done.set()


_reader: _Reader | None = None
_reader_lock = threading.Lock()


def focused_text(timeout: float = DEFAULT_TIMEOUT_SEC) -> str | None:
    """The focused box's text, or None (no box, no value, a password field,
    VoxScribe's own window, a timeout). Never raises. Call it off the UI
    thread: it can wait up to about `timeout` seconds."""
    global _reader
    try:
        if _foreground_is_this_process():
            return None
        with _reader_lock:
            if _reader is None:
                _reader = _Reader()
        return _reader.ask(timeout)
    except Exception:  # noqa: BLE001
        return None
