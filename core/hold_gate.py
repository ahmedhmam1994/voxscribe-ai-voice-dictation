"""Turns a key you also type with (Shift) into a safe hold-to-talk trigger.

A plain hotkey on Shift would start recording on every capital letter. This
gate only activates when the key is held *alone* for `delay` seconds: any
other key pressed first (a letter, an arrow, Ctrl) cancels it, as does
releasing early. Once active, releasing the key fires `on_deactivate`.

Pure state machine with an injectable timer so it can be unit tested without
real keyboard hooks or real waiting.
"""

from __future__ import annotations

import threading
from collections.abc import Callable


class HoldGate:
    def __init__(
        self,
        on_activate: Callable[[], None],
        on_deactivate: Callable[[], None],
        delay: float = 0.35,
        timer_factory: Callable[[float, Callable[[], None]], threading.Timer] = threading.Timer,
    ) -> None:
        self._on_activate = on_activate
        self._on_deactivate = on_deactivate
        self._delay = delay
        self._timer_factory = timer_factory
        self._lock = threading.Lock()
        self._down = False
        self._blocked = False
        self._active = False
        self._timer: threading.Timer | None = None

    def key_down(self, other_modifier_held: bool = False) -> None:
        with self._lock:
            if self._down:
                return  # key-repeat
            self._down = True
            self._blocked = other_modifier_held
            self._active = False
            if self._blocked:
                return
            self._timer = self._timer_factory(self._delay, self._fire)
            self._timer.daemon = True
            self._timer.start()

    def other_key_down(self) -> None:
        with self._lock:
            if self._down and not self._active:
                self._blocked = True
                self._cancel_timer()

    def key_up(self) -> None:
        with self._lock:
            was_active = self._active
            self._cancel_timer()
            self._down = False
            self._blocked = False
            self._active = False
        if was_active:
            self._on_deactivate()

    def _fire(self) -> None:
        with self._lock:
            if not self._down or self._blocked or self._active:
                return
            self._active = True
        self._on_activate()

    def _cancel_timer(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
