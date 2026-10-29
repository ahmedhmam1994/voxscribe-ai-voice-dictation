import dataclasses
import hashlib
import io
import tarfile

import numpy as np
import pytest

from core import engines


class _FakeWhisper:
    device = "cpu"

    def __init__(self):
        self.calls = []

    def transcribe(self, audio, language="en", initial_prompt=None, task="transcribe", beam_size=1):
        self.calls.append((language, task))
        return "whisper text"

    def transcribe_file(self, *args, **kwargs):
        return "whisper file"

    def transcribe_file_segments(self, *args, **kwargs):
        return [(0.0, 1.0, "whisper")]

    def transcribe_file_detailed(self, *args, **kwargs):
        return [(0.0, 1.0, "whisper", [])]


class _FakeExtra:
    def __init__(self, model, fail=False):
        self.model = model
        self.fail = fail

    def transcribe(self, audio, language):
        if self.fail:
            raise RuntimeError("boom")
        return f"{self.model.id} text"


def _ready(monkeypatch, *ids):
    monkeypatch.setattr(engines, "is_ready", lambda model: model.id in ids)


AUDIO = np.zeros(16000, dtype=np.float32)


def test_registry_has_the_tested_models():
    assert set(engines.MODELS) == {"parakeet-unified-en", "parakeet-v3", "cohere-14", "moonshine-ar"}
    for model in engines.MODELS.values():
        assert len(model.sha256) == 64
        assert model.url.startswith("https://github.com/k2-fsa/sherpa-onnx/releases/")
    assert "ar" in engines.MODELS["cohere-14"].languages
    assert engines.MODELS["parakeet-unified-en"].languages == ("en",)
    assert "de" in engines.MODELS["parakeet-v3"].languages


def test_auto_picks_the_best_downloaded_model_for_the_language(monkeypatch):
    _ready(monkeypatch, "parakeet-unified-en", "parakeet-v3", "cohere-14", "moonshine-ar")
    router = engines.SpeechRouter(_FakeWhisper(), "auto")
    assert router.pick("en").id == "parakeet-unified-en"
    assert router.pick("ar").id == "cohere-14"
    assert router.pick("de").id == "parakeet-v3"
    assert router.pick("ja") is None  # no tested extra model: Whisper


def test_auto_falls_back_to_the_next_model_then_whisper(monkeypatch):
    _ready(monkeypatch, "moonshine-ar")
    router = engines.SpeechRouter(_FakeWhisper(), "auto")
    assert router.pick("ar").id == "moonshine-ar"
    assert router.pick("en") is None


def test_whisper_handles_autodetect_and_translation(monkeypatch):
    _ready(monkeypatch, "cohere-14", "parakeet-unified-en")
    router = engines.SpeechRouter(_FakeWhisper(), "auto")
    assert router.pick(None) is None
    assert router.pick("ar", "translate") is None


def test_a_chosen_model_is_used_only_for_its_languages(monkeypatch):
    _ready(monkeypatch, "parakeet-unified-en")
    router = engines.SpeechRouter(_FakeWhisper(), "parakeet-unified-en")
    assert router.pick("en").id == "parakeet-unified-en"
    assert router.pick("ar") is None


def test_a_model_that_is_not_downloaded_is_never_picked(monkeypatch):
    _ready(monkeypatch)
    router = engines.SpeechRouter(_FakeWhisper(), "cohere-14")
    assert router.pick("ar") is None


def test_router_uses_the_extra_model_and_whisper_otherwise(monkeypatch):
    _ready(monkeypatch, "cohere-14")
    whisper = _FakeWhisper()
    router = engines.SpeechRouter(whisper, "auto", loader=_FakeExtra)
    assert router.transcribe(AUDIO, language="ar") == "cohere-14 text"
    assert whisper.calls == []
    assert router.transcribe(AUDIO, language="en") == "whisper text"
    assert whisper.calls == [("en", "transcribe")]


def test_an_extra_model_error_falls_back_to_whisper_and_is_skipped_after(monkeypatch):
    _ready(monkeypatch, "cohere-14")
    whisper = _FakeWhisper()
    loads = []

    def loader(model):
        loads.append(model.id)
        return _FakeExtra(model, fail=True)

    router = engines.SpeechRouter(whisper, "auto", loader=loader)
    assert router.transcribe(AUDIO, language="ar") == "whisper text"
    assert router.transcribe(AUDIO, language="ar") == "whisper text"
    assert loads == ["cohere-14"]  # not retried


def test_a_model_that_cannot_load_falls_back_to_whisper(monkeypatch):
    _ready(monkeypatch, "cohere-14")

    def loader(model):
        raise OSError("corrupt file")

    router = engines.SpeechRouter(_FakeWhisper(), "auto", loader=loader)
    router.warm("ar")  # must not raise
    assert router.transcribe(AUDIO, language="ar") == "whisper text"


def test_only_one_extra_model_stays_loaded(monkeypatch):
    _ready(monkeypatch, "cohere-14", "parakeet-unified-en")
    loads = []

    def loader(model):
        loads.append(model.id)
        return _FakeExtra(model)

    router = engines.SpeechRouter(_FakeWhisper(), "auto", loader=loader)
    router.transcribe(AUDIO, language="ar")
    router.transcribe(AUDIO, language="ar")
    router.transcribe(AUDIO, language="en")
    router.transcribe(AUDIO, language="ar")
    assert loads == ["cohere-14", "parakeet-unified-en", "cohere-14"]


def test_files_always_go_to_whisper(monkeypatch):
    _ready(monkeypatch, "cohere-14")
    router = engines.SpeechRouter(_FakeWhisper(), "auto", loader=_FakeExtra)
    assert router.transcribe_file("a.mp3") == "whisper file"
    assert router.transcribe_file_segments("a.mp3")[0][2] == "whisper"
    assert router.transcribe_file_detailed("a.mp3")[0][2] == "whisper"


class _FakeRecognizer:
    def __init__(self):
        self.options = []
        self.rate = None

    def create_stream(self):
        outer = self

        class Stream:
            result = type("Result", (), {"text": " hello there "})()

            def set_option(self, key, value):
                outer.options.append((key, value))

            def accept_waveform(self, rate, audio):
                outer.rate = rate

        return Stream()

    def decode_stream(self, stream):
        pass


def test_sherpa_transcriber_returns_text_and_sets_the_cohere_language(monkeypatch):
    monkeypatch.setattr(engines, "looks_like_speech", lambda _a: True)
    recognizer = _FakeRecognizer()
    engine = engines.SherpaTranscriber(engines.MODELS["cohere-14"], recognizer=recognizer)
    audio = (np.ones(16000) * 0.1).astype(np.float32)
    assert engine.transcribe(audio, "ar") == "hello there"
    assert ("language", "ar") in recognizer.options
    assert recognizer.rate == 16000


def test_sherpa_transcriber_skips_silence():
    engine = engines.SherpaTranscriber(engines.MODELS["parakeet-v3"], recognizer=_FakeRecognizer())
    assert engine.transcribe(np.zeros(16000, dtype=np.float32), "en") == ""
    assert engine.transcribe(np.zeros(0, dtype=np.float32), "en") == ""


# --- download ---------------------------------------------------------------


def _archive_for(model, files):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:bz2") as tar:
        for name in files:
            data = b"x" * 10
            info = tarfile.TarInfo(f"{model.folder}/{name}")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


class _Resp:
    def __init__(self, data):
        self._data, self._pos = data, 0

    def read(self, n):
        chunk = self._data[self._pos : self._pos + n]
        self._pos += n
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fake_model(model, data, sha=None, size=None):
    return dataclasses.replace(
        model,
        archive_bytes=size or len(data),
        sha256=sha or hashlib.sha256(data).hexdigest(),
    )


def test_download_installs_a_complete_model(tmp_path, monkeypatch):
    monkeypatch.setattr(engines, "MODELS_DIR", tmp_path)
    base = engines.MODELS["moonshine-ar"]
    data = _archive_for(base, base.files)
    model = _fake_model(base, data)
    monkeypatch.setattr(engines.urllib.request, "urlopen", lambda *a, **k: _Resp(data))
    seen = []
    engines.download(model, seen.append)
    assert all((tmp_path / model.folder / name).is_file() for name in model.files)
    assert any("Downloading" in m for m in seen)
    assert any("Unpacking" in m for m in seen)
    assert not list(tmp_path.glob("voxscribe-model-*"))  # temp folder cleaned up


def test_download_rejects_a_wrong_checksum_and_installs_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(engines, "MODELS_DIR", tmp_path)
    base = engines.MODELS["moonshine-ar"]
    data = _archive_for(base, base.files)
    model = _fake_model(base, data, sha="0" * 64)
    monkeypatch.setattr(engines.urllib.request, "urlopen", lambda *a, **k: _Resp(data))
    with pytest.raises(OSError, match="checksum"):
        engines.download(model)
    assert not (tmp_path / model.folder).exists()


def test_download_rejects_a_cut_short_file(tmp_path, monkeypatch):
    monkeypatch.setattr(engines, "MODELS_DIR", tmp_path)
    base = engines.MODELS["moonshine-ar"]
    data = _archive_for(base, base.files)
    model = _fake_model(base, data, size=len(data) + 100)
    monkeypatch.setattr(engines.urllib.request, "urlopen", lambda *a, **k: _Resp(data))
    with pytest.raises(OSError, match="incomplete"):
        engines.download(model)


def test_download_rejects_an_archive_missing_files(tmp_path, monkeypatch):
    monkeypatch.setattr(engines, "MODELS_DIR", tmp_path)
    base = engines.MODELS["moonshine-ar"]
    data = _archive_for(base, base.files[:1])
    model = _fake_model(base, data)
    monkeypatch.setattr(engines.urllib.request, "urlopen", lambda *a, **k: _Resp(data))
    with pytest.raises(OSError, match="incomplete"):
        engines.download(model)


def test_is_ready_and_remove(tmp_path, monkeypatch):
    monkeypatch.setattr(engines, "MODELS_DIR", tmp_path)
    model = engines.MODELS["moonshine-ar"]
    assert not engines.is_ready(model)
    folder = tmp_path / model.folder
    folder.mkdir()
    for name in model.files:
        (folder / name).write_bytes(b"x")
    assert engines.is_ready(model)
    assert engines.downloaded_ids() == ["moonshine-ar"]
    engines.remove(model)
    assert not engines.is_ready(model)
