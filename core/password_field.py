"""Is the keyboard focus in a password box right now?

Dictation must never be typed into a password field: the text would be a
spoken password, it would land in the history, and a wrong word typed there
is invisible. The Android app hides its button in such fields; this is the
Windows side.

Two checks, cheapest first:

1. A classic Win32 edit control with the ES_PASSWORD style (older desktop
   apps, Windows' own dialogs). Plain user32 calls, instant.
2. UI Automation's IsPassword property on the focused element, which covers
   browsers (Chrome, Edge and Firefox mark <input type="password"> this way),
   modern WinUI/WPF apps and most password managers.

UI Automation is called through raw COM vtable calls with ctypes, so no new
dependency gets bundled. It runs on its own background thread with its own
COM apartment, and every question has a short timeout: an app that is hung
can stall a UI Automation call for seconds, and the hotkey must never wait
on that. A timeout counts as "not a password field", so a slow app never
blocks dictation; it only loses this extra protection for that moment.
"""

from __future__ import annotations

import ctypes
import os
import queue
import threading
import time
from ctypes import wintypes

_ES_PASSWORD = 0x0020
_GWL_STYLE = -16
_UIA_IS_PASSWORD_PROPERTY_ID = 30019
_VT_BOOL = 11

_CLSID_CUIAUTOMATION = "{ff48dba4-60ef-4201-aa87-54103eef594e}"
_IID_IUIAUTOMATION = "{30cbe57d-d9d0-452a-ab13-7ac5ac4825ee}"

# IUIAutomation: IUnknown (0-2), CompareElements, CompareRuntimeIds,
# GetRootElement, ElementFromHandle, ElementFromPoint, GetFocusedElement (8).
_IUIAUTOMATION_GET_FOCUSED_ELEMENT = 8
# IUIAutomationElement: IUnknown (0-2), SetFocus, GetRuntimeId, FindFirst,
# FindAll, FindFirstBuildCache, FindAllBuildCache, BuildUpdatedCache,
# GetCurrentPropertyValue (10).
_ELEMENT_GET_CURRENT_PROPERTY_VALUE = 10
# ... get_CurrentProcessId (20), get_CurrentControlType (21).
_ELEMENT_GET_CURRENT_CONTROL_TYPE = 21
_UIA_PANE_CONTROL_TYPE_ID = 50033
_IUNKNOWN_RELEASE = 2

DEFAULT_TIMEOUT_SEC = 0.5
# Chromium browsers (Chrome, Edge, Electron apps) only build their
# accessibility tree once a UI Automation client first asks, so that very
# first answer is the bare window pane instead of the text box. One short
# retry gets the real element; later questions are answered at once.
_CHROMIUM_WAKE_SEC = 0.15


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class _VARIANT(ctypes.Structure):
    # 24 bytes on 64-bit: the type tag, three reserved words, then the value.
    _fields_ = [
        ("vt", ctypes.c_ushort),
        ("reserved1", ctypes.c_ushort),
        ("reserved2", ctypes.c_ushort),
        ("reserved3", ctypes.c_ushort),
        ("value", ctypes.c_longlong),
        ("extra", ctypes.c_longlong),
    ]


class _GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


def _foreground_is_this_process() -> bool:
    user32 = ctypes.windll.user32
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), ctypes.byref(pid))
    return pid.value == os.getpid()


def _win32_focus_is_password() -> bool:
    """A classic Edit control with ES_PASSWORD has the focus."""
    user32 = ctypes.windll.user32
    info = _GUITHREADINFO(cbSize=ctypes.sizeof(_GUITHREADINFO))
    if not user32.GetGUIThreadInfo(0, ctypes.byref(info)) or not info.hwndFocus:
        return False
    class_name = ctypes.create_unicode_buffer(64)
    user32.GetClassNameW(info.hwndFocus, class_name, 64)
    if "edit" not in class_name.value.lower():
        return False
    user32.GetWindowLongW.restype = ctypes.c_long
    style = user32.GetWindowLongW(info.hwndFocus, _GWL_STYLE)
    return bool(style & _ES_PASSWORD)


def _com_method(obj: ctypes.c_void_p, index: int, *argtypes):  # noqa: ANN202
    vtable = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    prototype = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, *argtypes)
    return prototype(vtable[index])


def _release(obj: ctypes.c_void_p) -> None:
    if obj:
        prototype = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)
        vtable = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        prototype(vtable[_IUNKNOWN_RELEASE])(obj)


def _guid(text: str) -> _GUID:
    guid = _GUID()
    ctypes.oledll.ole32.CLSIDFromString(ctypes.c_wchar_p(text), ctypes.byref(guid))
    return guid


class _UiaWorker:
    """Owns the UI Automation object on one background thread and answers
    "is the focused element a password field?" questions with a timeout."""

    def __init__(self) -> None:
        self._requests: queue.Queue[tuple[threading.Event, list[bool]]] = queue.Queue()
        self._busy = threading.Event()
        self._thread = threading.Thread(target=self._run, name="uia-password", daemon=True)
        self._thread.start()

    def ask(self, timeout: float) -> bool:
        if self._busy.is_set():
            # Still stuck on an earlier question (a hung app); don't queue
            # behind it and make this one wait too.
            return False
        done = threading.Event()
        answer: list[bool] = []
        self._requests.put((done, answer))
        if not done.wait(timeout):
            return False
        return bool(answer and answer[0])

    def _run(self) -> None:
        ole32 = ctypes.oledll.ole32
        try:
            ole32.CoInitializeEx(None, 0)  # COINIT_MULTITHREADED
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
                answer.append(bool(automation) and self._focused_is_password(automation))
            except Exception:  # noqa: BLE001
                answer.append(False)
            finally:
                self._busy.clear()
                done.set()

    @classmethod
    def _focused_is_password(cls, automation: ctypes.c_void_p) -> bool:
        is_password, is_pane = cls._ask_focused(automation)
        if not is_password and is_pane:
            time.sleep(_CHROMIUM_WAKE_SEC)
            is_password, _ = cls._ask_focused(automation)
        return is_password

    @staticmethod
    def _ask_focused(automation: ctypes.c_void_p) -> tuple[bool, bool]:
        """(focused element is a password field, focused element is a bare pane)."""
        element = ctypes.c_void_p()
        get_focused = _com_method(
            automation, _IUIAUTOMATION_GET_FOCUSED_ELEMENT, ctypes.POINTER(ctypes.c_void_p)
        )
        try:
            get_focused(automation, ctypes.byref(element))
        except OSError:
            return False, False
        if not element:
            return False, False
        try:
            control_type = ctypes.c_int()
            get_type = _com_method(
                element, _ELEMENT_GET_CURRENT_CONTROL_TYPE, ctypes.POINTER(ctypes.c_int)
            )
            get_type(element, ctypes.byref(control_type))
            is_pane = control_type.value == _UIA_PANE_CONTROL_TYPE_ID
            value = _VARIANT()
            get_property = _com_method(
                element,
                _ELEMENT_GET_CURRENT_PROPERTY_VALUE,
                ctypes.c_int,
                ctypes.POINTER(_VARIANT),
            )
            get_property(element, _UIA_IS_PASSWORD_PROPERTY_ID, ctypes.byref(value))
            # VARIANT_BOOL: -1 (0xFFFF) is true, 0 is false.
            is_password = value.vt == _VT_BOOL and (value.value & 0xFFFF) != 0
            ctypes.oledll.oleaut32.VariantClear(ctypes.byref(value))
            return is_password, is_pane
        except OSError:
            return False, False
        finally:
            _release(element)


_worker: _UiaWorker | None = None
_worker_lock = threading.Lock()


def focused_is_password(timeout: float = DEFAULT_TIMEOUT_SEC) -> bool:
    """True if the keyboard focus is in a password field. Never raises, and
    never waits longer than about `timeout` seconds."""
    global _worker
    try:
        if _foreground_is_this_process():
            # VoxScribe's own window. Asking UI Automation about it from here
            # would wait on this app's own (busy) UI thread until the timeout.
            return False
        if _win32_focus_is_password():
            return True
    except Exception:  # noqa: BLE001
        pass
    try:
        with _worker_lock:
            if _worker is None:
                _worker = _UiaWorker()
        return _worker.ask(timeout)
    except Exception:  # noqa: BLE001
        return False
