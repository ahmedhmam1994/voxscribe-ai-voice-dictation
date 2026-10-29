import subprocess

from core import read_aloud


class FakeProcess:
    def __init__(self) -> None:
        self.terminated = False

    def poll(self):
        return 0 if self.terminated else None

    def terminate(self) -> None:
        self.terminated = True


def _patch_popen(monkeypatch):
    calls = []

    def fake_popen(args, **kwargs):
        process = FakeProcess()
        calls.append((args, kwargs, process))
        return process

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    read_aloud._process = None
    return calls


def test_text_travels_in_the_environment_not_the_command_line(monkeypatch):
    calls = _patch_popen(monkeypatch)
    text = 'He said "hello"; $(rm -rf) & more'
    assert read_aloud.speak(text)
    args, kwargs, _process = calls[0]
    assert text not in " ".join(args)
    assert kwargs["env"]["VOXSCRIBE_SPEAK"] == text
    assert args[0] == "powershell.exe"
    assert read_aloud.is_speaking()


def test_a_new_reading_stops_the_old_one(monkeypatch):
    calls = _patch_popen(monkeypatch)
    read_aloud.speak("first")
    read_aloud.speak("second")
    assert calls[0][2].terminated
    assert not calls[1][2].terminated


def test_stop_ends_the_reading(monkeypatch):
    calls = _patch_popen(monkeypatch)
    read_aloud.speak("hello")
    read_aloud.stop()
    assert calls[0][2].terminated
    assert not read_aloud.is_speaking()


def test_empty_text_reads_nothing(monkeypatch):
    calls = _patch_popen(monkeypatch)
    assert not read_aloud.speak("   ")
    assert calls == []


def test_very_long_text_is_cut(monkeypatch):
    calls = _patch_popen(monkeypatch)
    read_aloud.speak("a" * 10000)
    assert len(calls[0][1]["env"]["VOXSCRIBE_SPEAK"]) == read_aloud.MAX_CHARS


def test_missing_powershell_is_not_a_crash(monkeypatch):
    def broken(*_args, **_kwargs):
        raise OSError("no powershell")

    monkeypatch.setattr(subprocess, "Popen", broken)
    read_aloud._process = None
    assert not read_aloud.speak("hello")
    assert not read_aloud.is_speaking()
