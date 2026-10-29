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


def test_weak_steady_noise_is_not_sent_to_whisper(monkeypatch):
    class Boom:
        def transcribe(self, *a, **k):
            raise AssertionError("background noise must not reach the model")

    monkeypatch.setattr(transcribe, "WhisperModel", lambda *a, **k: Boom())
    t = transcribe.Transcriber("small")
    rng = np.random.default_rng(1)
    hiss = (rng.standard_normal(32000) * 0.0008).astype(np.float32)
    assert t.transcribe(hiss) == ""


def test_quiet_but_clean_voice_is_accepted():
    # A quiet mic: voice peaks near 0.017 over a noise floor near 0.0005.
    rng = np.random.default_rng(2)
    audio = (rng.standard_normal(32000) * 0.0005).astype(np.float32)
    t = np.arange(8000)
    audio[12000:20000] += (np.sin(t * 0.3) * 0.012 * np.hanning(8000)).astype(np.float32)
    assert transcribe.looks_like_speech(audio)


def test_loud_recording_is_always_accepted():
    loud = (np.sin(np.linspace(0, 200, 16000)) * 0.2).astype(np.float32)
    assert transcribe.looks_like_speech(loud)


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
    assert (
        transcribe.model_cache_dir("large-v3-turbo").name
        == "models--mobiuslabsgmbh--faster-whisper-large-v3-turbo"
    )


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


def _make_model_bin(size_name, tmp_path, monkeypatch, nbytes=2_000_000):
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
    snap = transcribe.model_cache_dir(size_name) / "snapshots" / "abc"
    snap.mkdir(parents=True)
    (snap / "model.bin").write_bytes(b"\0" * nbytes)
    return transcribe.model_cache_dir(size_name)


def test_locked_file_is_retried_without_deleting_the_cache(monkeypatch, tmp_path):
    cache = _make_model_bin("small", tmp_path, monkeypatch)
    sleeps = []
    monkeypatch.setattr(transcribe.time, "sleep", lambda s: sleeps.append(s))
    calls = {"n": 0}

    def fake_model(*a, **k):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise RuntimeError("Unable to open file 'model.bin' in model 'x'")
        return object()

    monkeypatch.setattr(transcribe, "WhisperModel", fake_model)
    transcribe.load_transcriber("small")
    assert calls["n"] == 3
    assert sleeps == [3, 6]
    assert cache.exists()


def test_persistent_failure_still_purges_after_retries(monkeypatch, tmp_path):
    cache = _make_model_bin("small", tmp_path, monkeypatch)
    sleeps = []
    monkeypatch.setattr(transcribe.time, "sleep", lambda s: sleeps.append(s))
    calls = {"n": 0}

    def fake_model(*a, **k):
        calls["n"] += 1
        if calls["n"] <= 4:  # first load plus all three retries fail
            raise RuntimeError("Unable to open file 'model.bin' in model 'x'")
        return object()

    monkeypatch.setattr(transcribe, "WhisperModel", fake_model)
    transcribe.load_transcriber("small")
    assert sleeps == [3, 6, 12]
    assert calls["n"] == 5
    assert not cache.exists()


def test_missing_model_bin_purges_immediately(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
    cache = transcribe.model_cache_dir("small")
    (cache / "blobs").mkdir(parents=True)
    sleeps = []
    monkeypatch.setattr(transcribe.time, "sleep", lambda s: sleeps.append(s))
    calls = {"n": 0}

    def fake_model(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("File model.bin is incomplete")
        return object()

    monkeypatch.setattr(transcribe, "WhisperModel", fake_model)
    transcribe.load_transcriber("small")
    assert sleeps == []
    assert not cache.exists()


class _FailingModel:
    def transcribe(self, *args, **kwargs):
        def boom():
            raise RuntimeError("CUDA out of memory")
            yield  # pragma: no cover

        return boom(), None


class _Seg:
    text = " hello "


class _WorkingModel:
    def transcribe(self, *args, **kwargs):
        return iter([_Seg()]), None


def _gpu_transcriber(monkeypatch, loads):
    def fake_model(size, device, compute_type, local_files_only):
        loads.append(device)
        return _FailingModel() if device == "cuda" else _WorkingModel()

    monkeypatch.setattr(transcribe, "WhisperModel", fake_model)
    return transcribe.Transcriber("small", device="cuda", compute_type="float16")


def test_gpu_failure_mid_transcription_falls_back_to_cpu(monkeypatch):
    import numpy as np

    loads = []
    t = _gpu_transcriber(monkeypatch, loads)
    audio = (np.sin(np.linspace(0, 400, 16000)) * 0.5).astype("float32")
    monkeypatch.setattr(transcribe, "looks_like_speech", lambda _a: True)
    assert t.transcribe(audio) == "hello"
    assert loads == ["cuda", "cpu"]
    assert t.device == "cpu"


def test_gpu_that_cannot_load_falls_back_to_cpu(monkeypatch):
    def fake_model(size, device, compute_type, local_files_only):
        if device == "cuda":
            raise RuntimeError("cudaErrorInvalidDevice")
        return _WorkingModel()

    monkeypatch.setattr(transcribe, "WhisperModel", fake_model)
    t = transcribe.Transcriber("small", device="cuda", compute_type="float16")
    assert (t.device, t.compute_type) == ("cpu", "int8")


def test_cpu_errors_are_not_swallowed(monkeypatch):
    monkeypatch.setattr(transcribe, "WhisperModel", lambda *a, **k: _FailingModel())
    t = transcribe.Transcriber("small")
    monkeypatch.setattr(transcribe, "looks_like_speech", lambda _a: True)
    import numpy as np

    with pytest.raises(RuntimeError):
        t.transcribe((np.ones(16000) * 0.5).astype("float32"))
