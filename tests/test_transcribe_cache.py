"""Tests for the model-cache repair helpers and silence handling in
core/transcribe.py. Uses a fake faster-whisper model, never downloads one."""

import numpy as np
import pytest

from core import transcribe


def test_empty_audio_returns_empty_string(monkeypatch):
    monkeypatch.setattr(transcribe, "WhisperModel", lambda *a, **k: object())
    t = transcribe.Transcriber("small")
    assert t.transcribe(np.zeros(0, dtype=np.float32)) == ""


def test_near_silence_is_not_sent_to_whisper(monkeypatch):
    class Boom:
        def transcribe(self, *a, **k):
            raise AssertionError("silent audio must not reach the model")

    monkeypatch.setattr(transcribe, "WhisperModel", lambda *a, **k: Boom())
    t = transcribe.Transcriber("small")
    quiet = (np.random.randn(16000) * 1e-6).astype(np.float32)
    assert t.transcribe(quiet) == ""


def test_normal_quiet_speech_still_reaches_model(monkeypatch):
    class Seg:
        text = " hello "

    class Fake:
        def transcribe(self, audio, **k):
            assert abs(np.max(np.abs(audio)) - 0.5) < 1e-3
            return [Seg()], None

    monkeypatch.setattr(transcribe, "WhisperModel", lambda *a, **k: Fake())
    t = transcribe.Transcriber("small")
    speech = (np.sin(np.linspace(0, 200, 16000)) * 0.05).astype(np.float32)
    assert t.transcribe(speech) == "hello"


def test_model_cache_dir_names(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
    assert transcribe.model_cache_dir("small").name == "models--Systran--faster-whisper-small"
    assert transcribe.model_cache_dir("large").name == "models--Systran--faster-whisper-large-v3"


def test_purge_removes_only_that_model(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
    small = transcribe.model_cache_dir("small")
    base = transcribe.model_cache_dir("base")
    for d in (small, base):
        (d / "blobs").mkdir(parents=True)
        (d / "blobs" / "x").write_bytes(b"123")
    assert transcribe.model_cache_bytes("small") == 3
    assert transcribe.purge_model_cache("small") is True
    assert not small.exists()
    assert base.exists()
    assert transcribe.purge_model_cache("small") is False


def test_load_repairs_broken_cache_once(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
    d = transcribe.model_cache_dir("small")
    (d / "blobs").mkdir(parents=True)
    calls = {"n": 0}

    def fake_model(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("Unable to open file 'model.bin' in model 'x'")
        return object()

    monkeypatch.setattr(transcribe, "WhisperModel", fake_model)
    transcribe.load_transcriber("small")
    assert calls["n"] == 2
    assert not d.exists()


def test_load_does_not_purge_on_network_error(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
    d = transcribe.model_cache_dir("small")
    (d / "blobs").mkdir(parents=True)

    def fake_model(*a, **k):
        raise OSError("Cannot reach the server")

    monkeypatch.setattr(transcribe, "WhisperModel", fake_model)
    with pytest.raises(OSError):
        transcribe.load_transcriber("small")
    assert d.exists()


def test_unrelated_load_errors_do_not_purge(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
    d = transcribe.model_cache_dir("small")
    (d / "blobs").mkdir(parents=True)

    def fake_model(*a, **k):
        raise ValueError("Invalid compute type: float99")

    monkeypatch.setattr(transcribe, "WhisperModel", fake_model)
    with pytest.raises(ValueError):
        transcribe.load_transcriber("small")
    assert d.exists()
