import pytest
from PySide6.QtCore import QMimeData

from app import ask_key


class FakeClipboard:
    """Stands in for the system clipboard, so no QApplication is needed."""

    def __init__(self, text):
        self._data = QMimeData()
        self._data.setText(text)

    def setText(self, text):  # noqa: N802 -- Qt's name
        self._data = QMimeData()
        self._data.setText(text)

    def text(self):
        return self._data.text()

    def mimeData(self):  # noqa: N802
        return self._data

    def setMimeData(self, data):  # noqa: N802
        self._data = data

    def clear(self):
        self._data = QMimeData()


class FakeApp:
    def __init__(self):
        self._clip = FakeClipboard("what the user had copied")

    def clipboard(self):
        return self._clip


@pytest.fixture
def grabber(monkeypatch):
    app = FakeApp()
    monkeypatch.setattr(ask_key, "QApplication", app)
    sent = []
    seq = {"n": 100}
    monkeypatch.setattr(ask_key, "foreground_window_handle", lambda: 1)
    monkeypatch.setattr(ask_key, "foreground_process_name", lambda: "msedge.exe")
    monkeypatch.setattr(ask_key, "focused_is_password", lambda: False)
    monkeypatch.setattr(ask_key, "_clipboard_sequence", lambda: seq["n"])
    monkeypatch.setattr(ask_key.keyboard, "send", lambda keys: sent.append(keys))
    g = ask_key.SelectionGrabber()
    g._timer.stop = lambda: None  # driven by hand below
    g._timer.start = lambda: None
    return g, sent, seq, app


def _poll(g, times):
    for _ in range(times):
        if g.done:
            return
        g._poll()


def test_a_dropped_copy_is_sent_once_more(grabber):
    g, sent, seq, app = grabber
    g.grab()
    _poll(g, ask_key._RESEND_AT)
    assert sent == ["ctrl+c", "ctrl+c"] and not g.done
    app.clipboard().setText("the selected text")
    seq["n"] += 1  # the second copy landed
    _poll(g, 1)
    assert g.done and g.text == "the selected text"
    assert app.clipboard().text() == "what the user had copied"


def test_nothing_selected_gives_up_after_the_window(grabber):
    g, sent, _, app = grabber
    g.grab()
    _poll(g, ask_key._POLL_TRIES + 5)
    assert g.done and g.text == ""
    assert sent == ["ctrl+c", "ctrl+c"]
    assert app.clipboard().text() == "what the user had copied"


def test_a_quick_copy_is_not_sent_twice(grabber):
    g, sent, seq, app = grabber
    g.grab()
    app.clipboard().setText("picked")
    seq["n"] += 1
    _poll(g, 1)
    assert g.done and g.text == "picked" and sent == ["ctrl+c"]
