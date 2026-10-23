"""The tray menu's "Dictation language" submenu: one checkable entry per
language, so a bilingual user can switch without opening Settings. It reads and
writes through the two callbacks it is given (the app passes core/settings'
get_language and set_language), so the menu, the Settings dialog and the
language badge always agree."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QMenu


class LanguageMenu:
    def __init__(
        self,
        owner: QObject,
        menu: QMenu,
        languages: Iterable[tuple[str | None, str]],
        get_language: Callable[[], str | None],
        set_language: Callable[[str | None], None],
        on_changed: Callable[[str | None, str], None] | None = None,
    ) -> None:
        self._get = get_language
        self._set = set_language
        self._on_changed = on_changed
        self._names: dict[str | None, str] = {}
        self._actions: dict[str | None, QAction] = {}

        self.submenu = menu.addMenu("Dictation language")
        self._group = QActionGroup(owner)
        self._group.setExclusive(True)
        for code, name in languages:
            action = QAction(name, owner)
            action.setCheckable(True)
            self._group.addAction(action)
            self.submenu.addAction(action)
            action.triggered.connect(lambda _checked=False, c=code: self.choose(c))
            self._names[code] = name
            self._actions[code] = action
        self.sync()

    def choose(self, code: str | None) -> None:
        """Switches to [code]. Choosing the language already in use changes nothing."""
        if code == self._get():
            self.sync()
            return
        self._set(code)
        self.sync()
        if self._on_changed is not None:
            self._on_changed(code, self._names.get(code, ""))

    def sync(self) -> None:
        """Ticks the language in use, which may have been changed from Settings."""
        current = self._get()
        for code, action in self._actions.items():
            action.setChecked(code == current)
