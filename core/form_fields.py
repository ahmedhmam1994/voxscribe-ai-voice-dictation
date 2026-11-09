"""Reads the text boxes of a window and fills them, for form fill
(core/form_fill.py): "Name Sam Lee, phone 0100 123 4567, email ..." puts each
part into the box with that label.

UI Automation lists every enabled text box, dropdown and date picker in the
window in screen order. A box's label is its UI Automation name (browsers build it from
the <label>, aria-label or placeholder; classic dialogs from the text before
the box), else its help text, else its automation id ("inputEmail").
Password boxes and read-only boxes are left out.

Filling moves the keyboard focus to each box, checks the focus really
landed there, selects what the box holds and types the value with the same
keystrokes as normal dictation, so web pages see ordinary typing. A dropdown
gets its option's name typed (picking it the way typing does in a list), and
a date picker gets the digits of each part in the order the page shows them. A box the
focus does not reach is skipped, never typed into blindly.

Labels stay in memory for the match only; nothing is saved, logged or sent.
Same raw COM calls as core/password_field.py, on a background thread of its
own with its own COM apartment.
"""

from __future__ import annotations

import ctypes
import queue
import threading
import time
from collections.abc import Callable

from core import form_fill
from core.password_field import (
    _CLSID_CUIAUTOMATION,
    _ELEMENT_GET_CURRENT_CONTROL_TYPE,
    _ELEMENT_GET_CURRENT_PROPERTY_VALUE,
    _IID_IUIAUTOMATION,
    _IUIAUTOMATION_GET_FOCUSED_ELEMENT,
    _UIA_IS_PASSWORD_PROPERTY_ID,
    _VARIANT,
    _VT_BOOL,
    _com_method,
    _guid,
    _release,
)

# IUIAutomation: CompareElements (3), ElementFromHandle (6), CreateTrueCondition
# (21), CreatePropertyCondition (23), CreateOrCondition (28).
_IUIAUTOMATION_COMPARE_ELEMENTS = 3
_IUIAUTOMATION_ELEMENT_FROM_HANDLE = 6
_IUIAUTOMATION_CREATE_TRUE_CONDITION = 21
_IUIAUTOMATION_CREATE_PROPERTY_CONDITION = 23
_IUIAUTOMATION_CREATE_OR_CONDITION = 28
# IUIAutomationElement: SetFocus (3), FindAll (6).
_ELEMENT_SET_FOCUS = 3
_ELEMENT_FIND_ALL = 6
# IUIAutomationElementArray: get_Length (3), GetElement (4).
_ARRAY_LENGTH = 3
_ARRAY_GET = 4

_TREE_SCOPE_CHILDREN = 2
_TREE_SCOPE_DESCENDANTS = 4
_UIA_CONTROL_TYPE_PROPERTY_ID = 30003
_UIA_EDIT_CONTROL_TYPE_ID = 50004
_UIA_COMBO_BOX_CONTROL_TYPE_ID = 50003
_UIA_SPINNER_CONTROL_TYPE_ID = 50016
_UIA_LOCALIZED_CONTROL_TYPE_PROPERTY_ID = 30004
_UIA_NAME_PROPERTY_ID = 30005
_UIA_IS_ENABLED_PROPERTY_ID = 30010
_UIA_AUTOMATION_ID_PROPERTY_ID = 30011
_UIA_HELP_TEXT_PROPERTY_ID = 30013
_UIA_VALUE_IS_READ_ONLY_PROPERTY_ID = 30046
_UIA_VALUE_VALUE_PROPERTY_ID = 30045
_VT_I4 = 3
_VT_BSTR = 8

MAX_FIELDS = 60
MAX_LABEL_LENGTH = 80
# Chromium builds a page's accessibility tree only once a UI Automation
# client asks about it; a few short retries find the boxes it had not
# reported yet.
_WAKE_TRIES = (0.3, 0.6)
_FOCUS_SETTLE_SEC = 0.06


def _variant_property(element: ctypes.c_void_p, property_id: int) -> _VARIANT:
    value = _VARIANT()
    get_property = _com_method(
        element, _ELEMENT_GET_CURRENT_PROPERTY_VALUE, ctypes.c_int, ctypes.POINTER(_VARIANT)
    )
    get_property(element, property_id, ctypes.byref(value))
    return value


def _bool_property(element: ctypes.c_void_p, property_id: int) -> bool | None:
    value = _variant_property(element, property_id)
    try:
        if value.vt != _VT_BOOL:
            return None
        return (value.value & 0xFFFF) != 0
    finally:
        ctypes.oledll.oleaut32.VariantClear(ctypes.byref(value))


def _text_property(element: ctypes.c_void_p, property_id: int) -> str:
    value = _variant_property(element, property_id)
    try:
        if value.vt != _VT_BSTR or not value.value:
            return ""
        return ctypes.wstring_at(value.value).strip()
    finally:
        ctypes.oledll.oleaut32.VariantClear(ctypes.byref(value))


def _label(element: ctypes.c_void_p) -> str:
    """The first of name, help text and automation id that has words."""
    for property_id in (_UIA_NAME_PROPERTY_ID, _UIA_HELP_TEXT_PROPERTY_ID):
        text = _text_property(element, property_id)
        if text and len(text) <= MAX_LABEL_LENGTH and form_fill.aliases(text):
            return text
    return form_fill.label_from_id(_text_property(element, _UIA_AUTOMATION_ID_PROPERTY_ID)) or ""


def _type_condition(automation: ctypes.c_void_p, control_type: int) -> ctypes.c_void_p:
    condition = ctypes.c_void_p()
    kind = _VARIANT()
    kind.vt = _VT_I4
    kind.value = control_type
    _com_method(
        automation,
        _IUIAUTOMATION_CREATE_PROPERTY_CONDITION,
        ctypes.c_int,
        _VARIANT,
        ctypes.POINTER(ctypes.c_void_p),
    )(automation, _UIA_CONTROL_TYPE_PROPERTY_ID, kind, ctypes.byref(condition))
    return condition


def _found(array: ctypes.c_void_p, limit: int) -> list[ctypes.c_void_p]:
    """The elements of an IUIAutomationElementArray, which is released."""
    found: list[ctypes.c_void_p] = []
    if not array:
        return found
    try:
        length = ctypes.c_int()
        _com_method(array, _ARRAY_LENGTH, ctypes.POINTER(ctypes.c_int))(
            array, ctypes.byref(length)
        )
        get = _com_method(array, _ARRAY_GET, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p))
        for i in range(min(length.value, limit)):
            element = ctypes.c_void_p()
            get(array, i, ctypes.byref(element))
            if element:
                found.append(element)
        return found
    finally:
        _release(array)


def _find_all(
    element: ctypes.c_void_p, scope: int, condition: ctypes.c_void_p, limit: int
) -> list[ctypes.c_void_p]:
    array = ctypes.c_void_p()
    _com_method(
        element, _ELEMENT_FIND_ALL, ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)
    )(element, scope, condition, ctypes.byref(array))
    return _found(array, limit)


def _control_type(element: ctypes.c_void_p) -> int:
    value = ctypes.c_int()
    _com_method(element, _ELEMENT_GET_CURRENT_CONTROL_TYPE, ctypes.POINTER(ctypes.c_int))(
        element, ctypes.byref(value)
    )
    return value.value


def _date_parts(
    automation: ctypes.c_void_p, element: ctypes.c_void_p
) -> tuple[str, ctypes.c_void_p | None]:
    """("MDY" or "DMY"..., the first part to focus) for a date picker: the
    order of its parts comes from the names of its spin buttons ("Month Date
    of birth"); month, day, year when they do not say. Typing starts in the
    first part and moves on by itself. The caller releases the part."""
    condition = ctypes.c_void_p()
    _com_method(automation, _IUIAUTOMATION_CREATE_TRUE_CONDITION, ctypes.POINTER(ctypes.c_void_p))(
        automation, ctypes.byref(condition)
    )
    order = ""
    first_part: ctypes.c_void_p | None = None
    try:
        for child in _find_all(element, _TREE_SCOPE_CHILDREN, condition, 12):
            keep = False
            try:
                if _control_type(child) == _UIA_SPINNER_CONTROL_TYPE_ID:
                    first = _text_property(child, _UIA_NAME_PROPERTY_ID).split(" ")[0].lower()
                    letter = {"month": "M", "day": "D", "year": "Y"}.get(first)
                    if letter and letter not in order:
                        order += letter
                    if first_part is None:
                        first_part, keep = child, True
            finally:
                if not keep:
                    _release(child)
    finally:
        _release(condition)
    return (order if sorted(order) == ["D", "M", "Y"] else "MDY"), first_part


def _edit_elements(automation: ctypes.c_void_p, hwnd: int) -> list[ctypes.c_void_p]:
    """Every text box and dropdown under the window, in tree (screen) order.
    The caller releases them."""
    root = ctypes.c_void_p()
    from_handle = _com_method(
        automation,
        _IUIAUTOMATION_ELEMENT_FROM_HANDLE,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    )
    from_handle(automation, hwnd, ctypes.byref(root))
    if not root:
        return []
    edits = _type_condition(automation, _UIA_EDIT_CONTROL_TYPE_ID)
    combos = _type_condition(automation, _UIA_COMBO_BOX_CONTROL_TYPE_ID)
    either = ctypes.c_void_p()
    try:
        _com_method(
            automation,
            _IUIAUTOMATION_CREATE_OR_CONDITION,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
        )(automation, edits, combos, ctypes.byref(either))
        return _find_all(root, _TREE_SCOPE_DESCENDANTS, either, MAX_FIELDS * 3)
    finally:
        _release(either)
        _release(combos)
        _release(edits)
        _release(root)


def _read_fields(
    automation: ctypes.c_void_p, hwnd: int
) -> tuple[list[form_fill.Field], list[ctypes.c_void_p], list[ctypes.c_void_p]]:
    """(the fields, their elements by field index, every element to release)."""
    elements = _edit_elements(automation, hwnd)
    extra: list[ctypes.c_void_p] = []
    fields: list[form_fill.Field] = []
    by_index: list[ctypes.c_void_p] = []
    for element in elements:
        if len(fields) >= MAX_FIELDS:
            break
        try:
            if _bool_property(element, _UIA_IS_PASSWORD_PROPERTY_ID):
                continue
            if _bool_property(element, _UIA_IS_ENABLED_PROPERTY_ID) is False:
                continue
            is_combo = _control_type(element) == _UIA_COMBO_BOX_CONTROL_TYPE_ID
            # A list you pick from reports itself read-only; it still takes a choice.
            if not is_combo and _bool_property(element, _UIA_VALUE_IS_READ_ONLY_PROPERTY_ID):
                continue
            label = _label(element)
            kind, pattern = form_fill.kind_of_label(label), ""
            target = element
            if is_combo:
                kind = form_fill.CHOICE
            elif _text_property(element, _UIA_LOCALIZED_CONTROL_TYPE_PROPERTY_ID) == "date picker":
                kind = form_fill.DATE
                pattern, first_part = _date_parts(automation, element)
                if first_part is not None:
                    # The focus goes to a part, not the picker itself.
                    target = first_part
                    extra.append(first_part)
            elif kind == form_fill.TEXT:
                # A plain box whose hint shows a date format: "DD/MM/YYYY".
                pattern = form_fill.date_pattern(
                    _text_property(element, _UIA_HELP_TEXT_PROPERTY_ID)
                    + " "
                    + _text_property(element, _UIA_NAME_PROPERTY_ID)
                )
                if pattern:
                    kind = form_fill.DATE
        except OSError:
            continue
        fields.append(form_fill.Field(len(fields), label, kind, pattern))
        by_index.append(target)
    return fields, by_index, elements + extra


_UIA_LIST_ITEM_CONTROL_TYPE_ID = 50007
_UIA_SELECTION_ITEM_PATTERN_ID = 10010
_IID_SELECTION_ITEM_PATTERN = "{a8efa66a-0fda-421a-9194-38021f3578ea}"
# IUIAutomationElement::GetCurrentPatternAs (14); IUIAutomationSelectionItemPattern::Select (3).
_ELEMENT_GET_CURRENT_PATTERN_AS = 14
_SELECTION_ITEM_SELECT = 3
# Stepping through a closed dropdown: how long one option may take to show,
# and the most options read.
_STEP_WAIT_SEC = 0.4
_MAX_OPTIONS = 300


def _best_option(names: list[str], value: str) -> int | None:
    """The option said: the same name, else the one starting with it, else
    the one containing it. None when nothing matches."""
    wanted = " ".join(value.split()).casefold()
    if not wanted:
        return None
    folded = [" ".join(n.split()).casefold() for n in names]
    for test in (
        lambda n: n == wanted,
        lambda n: n.startswith(wanted),
        lambda n: wanted in n,
    ):
        for i, name in enumerate(folded):
            if name and test(name):
                return i
    return None


def _select_option(automation: ctypes.c_void_p, combo: ctypes.c_void_p, value: str) -> bool:
    """Picks the list item named `value` in a dropdown through UI Automation.
    False when the list does not show its items or none matches, so the name
    is typed instead."""
    condition = _type_condition(automation, _UIA_LIST_ITEM_CONTROL_TYPE_ID)
    items: list[ctypes.c_void_p] = []
    try:
        items = _find_all(combo, _TREE_SCOPE_DESCENDANTS, condition, 400)
        names = [_text_property(item, _UIA_NAME_PROPERTY_ID) for item in items]
        best = _best_option(names, value)
        if best is None:
            return False
        pattern = ctypes.c_void_p()
        iid = _guid(_IID_SELECTION_ITEM_PATTERN)
        _com_method(
            items[best],
            _ELEMENT_GET_CURRENT_PATTERN_AS,
            ctypes.c_int,
            ctypes.POINTER(type(iid)),
            ctypes.POINTER(ctypes.c_void_p),
        )(items[best], _UIA_SELECTION_ITEM_PATTERN_ID, ctypes.byref(iid), ctypes.byref(pattern))
        if not pattern:
            return False
        try:
            _com_method(pattern, _SELECTION_ITEM_SELECT)(pattern)
        finally:
            _release(pattern)
        return True
    except OSError:
        return False
    finally:
        for item in items:
            _release(item)
        _release(condition)


def _value_text(element: ctypes.c_void_p) -> str | None:
    """What the box shows, or None when it has no Value to read."""
    try:
        raw = _variant_property(element, _UIA_VALUE_VALUE_PROPERTY_ID)
    except OSError:
        return None
    try:
        if raw.vt != _VT_BSTR:
            return None
        return ctypes.wstring_at(raw.value) if raw.value else ""
    finally:
        ctypes.oledll.oleaut32.VariantClear(ctypes.byref(raw))


def _changed(element: ctypes.c_void_p, before: str) -> str | None:
    """Waits a moment for the box to show something new after a key press;
    None when it stays the same (the end of the list)."""
    deadline = time.monotonic() + _STEP_WAIT_SEC
    while time.monotonic() < deadline:
        time.sleep(0.02)
        now = _value_text(element)
        if now is not None and now != before:
            return now
    return None


def _step_to_option(element: ctypes.c_void_p, value: str) -> bool:
    """Picks an option in a closed dropdown with the arrow keys, which both
    classic lists and web pages answer: Home, then Down one option at a time
    reading the name shown, until the one said comes up. A list that hides its
    items (a classic combo, a page's select) still shows the chosen one."""
    import keyboard

    wanted = " ".join(value.split()).casefold()
    keyboard.send("home")
    time.sleep(0.08)
    current = _value_text(element)
    if current is None:
        return False
    names = [current]
    while len(names) < _MAX_OPTIONS:
        if " ".join(current.split()).casefold() == wanted:
            return True
        keyboard.send("down")
        following = _changed(element, current)
        if following is None:
            break
        current = following
        names.append(current)
    best = _best_option(names, value)
    if best is None:
        return False
    keyboard.send("home")
    time.sleep(0.08)
    for _ in range(best):
        keyboard.send("down")
        time.sleep(0.03)
    return True


def _wake(automation: ctypes.c_void_p) -> None:
    """Asks for the focused element, which makes Chromium build the page's
    accessibility tree."""
    focused = ctypes.c_void_p()
    try:
        _com_method(
            automation, _IUIAUTOMATION_GET_FOCUSED_ELEMENT, ctypes.POINTER(ctypes.c_void_p)
        )(automation, ctypes.byref(focused))
    except OSError:
        pass
    finally:
        _release(focused)


def _focus(automation: ctypes.c_void_p, element: ctypes.c_void_p) -> bool:
    """Moves the keyboard focus to `element`; True once it is really there."""
    try:
        _com_method(element, _ELEMENT_SET_FOCUS)(element)
    except OSError:
        return False
    get_focused = _com_method(
        automation, _IUIAUTOMATION_GET_FOCUSED_ELEMENT, ctypes.POINTER(ctypes.c_void_p)
    )
    compare = _com_method(
        automation,
        _IUIAUTOMATION_COMPARE_ELEMENTS,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_int),
    )
    for wait in (_FOCUS_SETTLE_SEC, 0.15):
        time.sleep(wait)
        focused = ctypes.c_void_p()
        try:
            get_focused(automation, ctypes.byref(focused))
            if not focused:
                continue
            same = ctypes.c_int()
            compare(automation, element, focused, ctypes.byref(same))
            if same.value:
                return True
        except OSError:
            continue
        finally:
            _release(focused)
    return False


def _holds(element: ctypes.c_void_p, value: str, field: form_fill.Field) -> bool | None:
    """True when the box now holds `value`, None when it does not say."""
    if field.kind == form_fill.DATE and field.pattern.isalpha():
        # A date picker shows its parts in the page's own format.
        return None
    try:
        raw = _variant_property(element, _UIA_VALUE_VALUE_PROPERTY_ID)
    except OSError:
        return None
    try:
        if raw.vt != _VT_BSTR:
            # No Value to read (a rich editor): trust the typing.
            return None
        text = ctypes.wstring_at(raw.value) if raw.value else ""
    finally:
        ctypes.oledll.oleaut32.VariantClear(ctypes.byref(raw))
    if field.kind == form_fill.CHOICE:
        # The option shown is the one said (the same rule that picked it).
        return _best_option([text], value) is not None
    return " ".join(text.split()) == " ".join(value.split())


def _fill_one(
    automation: ctypes.c_void_p,
    element: ctypes.c_void_p,
    field: form_fill.Field,
    value: str,
    type_value,
) -> bool:
    """Focuses the box, types `value` and checks it landed. A browser can
    take the first keystrokes before its page really has the focus, so a box
    that comes out wrong gets one more try."""
    for attempt in range(2):
        if not _focus(automation, element):
            return False
        # Checked again on the element itself, right before typing.
        if _bool_property(element, _UIA_IS_PASSWORD_PROPERTY_ID):
            return False
        if field.kind == form_fill.CHOICE and _select_option(automation, element, value):
            # Picked from the list itself, the way a click would.
            time.sleep(0.05)
            if _holds(element, value, field) is not False:
                return True
        if field.kind == form_fill.CHOICE and _step_to_option(element, value):
            time.sleep(0.05)
            if _holds(element, value, field) is not False:
                return True
        # A text box has what it holds replaced; a list or date picker
        # takes the typing as it is.
        picker = field.kind == form_fill.DATE and field.pattern.isalpha()
        type_value(value, field.kind != form_fill.CHOICE and not picker)
        time.sleep(0.05)
        holds = _holds(element, value, field)
        if holds is None or holds:
            return True
        if attempt == 0:
            time.sleep(0.2)
    return False


Planner = Callable[[list[form_fill.Field]], "list[form_fill.Fill] | None"]
# (the value, whether to select what the box holds first).
Typer = Callable[[str, bool], None]


def _fill_form(
    automation: ctypes.c_void_p, hwnd: int, planner: Planner, type_value: Typer
) -> tuple[int, int] | None:
    _wake(automation)
    fields, by_index, elements = _read_fields(automation, hwnd)
    try:
        fills = planner(fields)
        for wait in _WAKE_TRIES:
            if fills is not None:
                break
            # Chromium may not have built its page tree yet (only the address
            # bar shows on the first question): look again.
            for element in elements:
                _release(element)
            time.sleep(wait)
            _wake(automation)
            fields, by_index, elements = _read_fields(automation, hwnd)
            fills = planner(fields)
        if fills is None:
            return None
        filled = 0
        for fill in fills:
            if 0 <= fill.index < len(by_index) and _fill_one(
                automation, by_index[fill.index], fields[fill.index], fill.value, type_value
            ):
                filled += 1
        return filled, len(fills)
    finally:
        for element in elements:
            _release(element)


class _Worker:
    def __init__(self) -> None:
        self._requests: queue.Queue = queue.Queue()
        self._busy = threading.Event()
        threading.Thread(target=self._run, name="uia-form", daemon=True).start()

    def ask(self, job: Callable, timeout: float):  # noqa: ANN202
        if self._busy.is_set():
            return None
        done = threading.Event()
        answer: list = []
        self._requests.put((job, done, answer))
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
            job, done, answer = self._requests.get()
            self._busy.set()
            try:
                answer.append(job(automation) if automation else None)
            except Exception:  # noqa: BLE001
                answer.append(None)
            finally:
                self._busy.clear()
                done.set()


_worker: _Worker | None = None
_worker_lock = threading.Lock()


def _get_worker() -> _Worker:
    global _worker
    with _worker_lock:
        if _worker is None:
            _worker = _Worker()
        return _worker


def read_fields(hwnd: int, timeout: float = 3.0) -> list[form_fill.Field]:
    """The labelled boxes in the window, for checking what form fill sees.
    Never raises."""

    def job(automation: ctypes.c_void_p) -> list[form_fill.Field]:
        fields, _, elements = _read_fields(automation, hwnd)
        for element in elements:
            _release(element)
        return fields

    try:
        return _get_worker().ask(job, timeout) or []
    except Exception:  # noqa: BLE001
        return []


def fill_form(
    hwnd: int, planner: Planner, type_value: Typer, timeout: float = 60.0
) -> tuple[int, int] | None:
    """Reads the boxes in window `hwnd`, asks `planner` what goes where and
    types each value with `type_value` after moving the focus to its box.
    Returns (boxes filled, boxes planned), or None when the window holds no
    form for the sentence (nothing was typed). Call it off the UI thread.
    Never raises."""
    try:
        return _get_worker().ask(
            lambda automation: _fill_form(automation, hwnd, planner, type_value), timeout
        )
    except Exception:  # noqa: BLE001
        return None
