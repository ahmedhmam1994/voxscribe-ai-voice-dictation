"""The Ask key (Pro): the window side of core/ask_library.py and the
assistant's edit().

- SelectionGrabber reads the text selected in the focused app when the key
  goes down, with Ctrl+C, and then puts the clipboard back exactly as it was,
  so the user's clipboard is never lost.
- show_answer_dialog shows an answer from the Library next to the pieces it
  came from, so the user can check it.
"""

from __future__ import annotations

import ctypes

import keyboard
from PySide6.QtCore import QMimeData, QObject, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core import ask_library, library
from core.focused_window import foreground_process_name, foreground_window_handle
from core.password_field import focused_is_password

# Ctrl+C with nothing selected stops the running program in a terminal, so
# the selection is never read there: the Ask key asks the Library instead.
TERMINALS = frozenset(
    {
        "cmd.exe", "powershell.exe", "pwsh.exe", "windowsterminal.exe", "wt.exe",
        "conhost.exe", "openconsole.exe", "mintty.exe", "bash.exe", "wsl.exe",
        "alacritty.exe", "wezterm-gui.exe", "putty.exe", "kitty.exe",
    }
)  # fmt: skip
# Code editors copy the whole line when nothing is selected. That copy ends
# with a line break, so such a copy counts as no selection.
LINE_COPY_EDITORS = frozenset(
    {
        "code.exe", "code - insiders.exe", "cursor.exe", "windsurf.exe", "devenv.exe",
        "idea64.exe", "pycharm64.exe", "webstorm64.exe", "rider64.exe", "clion64.exe",
        "goland64.exe", "phpstorm64.exe", "rubymine64.exe", "studio64.exe",
        "sublime_text.exe",
    }
)  # fmt: skip

_POLL_MS = 60
_POLL_TRIES = 25  # about 1.5 s: Word and some browsers are slow to copy
# A Ctrl+C that lands while the window is still busy (a page just loaded, a
# key still settling) is sometimes dropped, so it is sent once more if the
# clipboard has not moved by then. A second copy of the same selection is
# harmless.
_RESEND_AT = 8  # about 0.5 s


def _clipboard_sequence() -> int:
    """Windows' clipboard change counter: it moves only if the copy worked."""
    try:
        return int(ctypes.windll.user32.GetClipboardSequenceNumber())
    except (AttributeError, OSError):
        return 0


def _clone(source: QMimeData | None) -> QMimeData:
    copy = QMimeData()
    if source is not None:
        for fmt in source.formats():
            copy.setData(fmt, source.data(fmt))
    return copy


class SelectionGrabber(QObject):
    """grab() on key down; `text` holds the selection once `done` is True.
    Nothing selected leaves `text` empty: most apps copy nothing then, so
    the clipboard counter does not move and nothing is touched."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.text = ""
        self.hwnd = None
        self.done = True
        self._before = 0
        self._process = ""
        self._saved: QMimeData | None = None
        self._tries = 0
        self._resent = False
        self._timer = QTimer(self)
        self._timer.setInterval(_POLL_MS)
        self._timer.timeout.connect(self._poll)

    def grab(self) -> None:
        self._timer.stop()
        self.text = ""
        self.hwnd = foreground_window_handle()
        self.done = True
        self._process = (foreground_process_name() or "").casefold()
        if self._process in TERMINALS or focused_is_password():
            return
        clipboard = QApplication.clipboard()
        self._saved = _clone(clipboard.mimeData())
        self._before = _clipboard_sequence()
        try:
            keyboard.send("ctrl+c")
        except Exception:  # noqa: BLE001 -- no selection is the safe outcome
            return
        self.done = False
        self._tries = 0
        self._resent = False
        self._timer.start()

    def _poll(self) -> None:
        self._tries += 1
        if _clipboard_sequence() != self._before:
            self._timer.stop()
            clipboard = QApplication.clipboard()
            copied = clipboard.text() or ""
            line_copy = self._process in LINE_COPY_EDITORS and copied.endswith("\n")
            self.text = "" if line_copy else copied.strip()
            saved, self._saved = self._saved, None
            if saved is not None and saved.formats():
                clipboard.setMimeData(saved)
            else:
                clipboard.clear()
            self.done = True
        elif self._tries >= _POLL_TRIES:
            self._timer.stop()
            self._saved = None
            self.done = True
        elif self._tries >= _RESEND_AT and not self._resent:
            self._resent = True
            try:
                keyboard.send("ctrl+c")
            except Exception:  # noqa: BLE001 -- the first copy may still land
                pass


def _source_line(source: ask_library.Source) -> str:
    when = ask_library.date_label(source.item.created)
    text = library.plain(source.excerpt)
    if len(text) > 220:
        text = text[:220].rsplit(" ", 1)[0] + "..."
    return f"{source.item.label}, {when}\n{text}"


def show_answer_dialog(
    parent: QWidget,
    question: str,
    answer: str | None,
    sources: list[ask_library.Source],
    note: str,
    stylesheet: str,
) -> None:
    """The answer, then the pieces of the Library it was given. Not modal,
    so the user can keep working while it is open."""
    dialog = QDialog(parent)
    dialog.setAttribute(Qt.WA_DeleteOnClose)
    dialog.setWindowTitle("Ask your past self")
    dialog.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    dialog.setStyleSheet(stylesheet)
    dialog.resize(600, 460)
    layout = QVBoxLayout(dialog)

    asked = QLabel(f"You asked: {question}")
    asked.setWordWrap(True)
    asked.setObjectName("hotkeyHint")
    layout.addWidget(asked)

    if answer:
        shown = answer
    elif sources:
        shown = "Your Library has notes that look related, but none of them answers this."
    else:
        shown = "Nothing in your Library mentions that."
    answer_view = QTextEdit()
    answer_view.setReadOnly(True)
    answer_view.setPlainText(shown)
    answer_view.setMaximumHeight(140)
    layout.addWidget(answer_view)

    if sources:
        heading = QLabel("FROM YOUR LIBRARY")
        heading.setObjectName("settingsSectionLabel")
        layout.addWidget(heading)
        source_view = QTextEdit()
        source_view.setReadOnly(True)
        source_view.setPlainText("\n\n".join(_source_line(source) for source in sources))
        layout.addWidget(source_view, stretch=1)
    else:
        layout.addStretch(1)

    hint = QLabel(
        "Answered on this PC from what you dictated, imported and noted. Nothing is sent "
        "anywhere. The model can still get things wrong, so check the notes above."
        + (f"\n{note}" if note else "")
    )
    hint.setWordWrap(True)
    hint.setObjectName("hotkeyHint")
    layout.addWidget(hint)

    buttons = QHBoxLayout()
    copy_button = QPushButton("Copy answer")
    close_button = QPushButton("Close")
    copy_button.setObjectName("primaryOutlineButton")
    close_button.setObjectName("secondaryButton")
    copy_button.setEnabled(bool(answer))
    for button in (copy_button, close_button):
        button.setCursor(Qt.PointingHandCursor)
    buttons.addStretch(1)
    buttons.addWidget(copy_button)
    buttons.addWidget(close_button)
    layout.addLayout(buttons)

    def copy() -> None:
        QApplication.clipboard().setText(answer or "")
        copy_button.setText("Copied")

    copy_button.clicked.connect(copy)
    close_button.clicked.connect(dialog.close)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
