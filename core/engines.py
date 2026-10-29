"""Extra speech models beyond Whisper, and the router that picks one per language.

Whisper (faster-whisper) stays the default and handles every language, file
imports and translation. On top of it, four optional models run through
sherpa-onnx, each downloaded only when the user asks for it:

- Parakeet Unified English: the most accurate and fastest on English.
- Parakeet v3: fast English and 24 other European languages.
- Cohere Transcribe: the most accurate on Arabic (Egyptian dialect included),
  plus 13 other languages.
- Moonshine Base Arabic: a small, fast Arabic model.

Picked by testing on recordings of one speaker (see marketing/model-test), not
by a vendor's table. Every model here runs on the CPU, offline.

`SpeechRouter` wraps the Whisper `Transcriber` and has the same methods, so the
rest of the app does not care which model answered. Anything the extra models
cannot do (an unsupported language, translation, file import with timestamps,
or any error) goes to Whisper, so dictation never fails because of them.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tarfile
import tempfile
import threading
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from core import unsure
from core.transcribe import looks_like_speech

_APP_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "VoxScribe"
MODELS_DIR = _APP_DIR / "models" / "sherpa"

_RELEASES = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models"

SPEECH_ENGINE_WHISPER = "whisper"
SPEECH_ENGINE_AUTO = "auto"


@dataclass(frozen=True)
class SherpaModel:
    id: str
    label: str
    description: str
    kind: str  # "parakeet", "cohere" or "moonshine_v2": which sherpa-onnx loader
    folder: str  # the archive's top-level folder inside MODELS_DIR
    archive: str
    archive_bytes: int
    sha256: str  # of the archive as published, checked before anything is unpacked
    download_mb: int
    languages: tuple[str, ...]
    files: tuple[str, ...]  # what must exist for the model to count as installed

    @property
    def url(self) -> str:
        return f"{_RELEASES}/{self.archive}"

    @property
    def path(self) -> Path:
        return MODELS_DIR / self.folder


_PARAKEET_V3_LANGUAGES = (
    "bg", "hr", "cs", "da", "nl", "en", "et", "fi", "fr", "de", "el", "hu", "it",
    "lv", "lt", "mt", "pl", "pt", "ro", "sk", "sl", "es", "sv", "ru", "uk",
)  # fmt: skip

_COHERE_LANGUAGES = (
    "en", "fr", "de", "it", "es", "pt", "el", "nl", "pl", "zh", "ja", "ko", "vi", "ar",
)  # fmt: skip

MODELS: dict[str, SherpaModel] = {
    m.id: m
    for m in (
        SherpaModel(
            id="parakeet-unified-en",
            label="Parakeet Unified English",
            description="Best English: about half the mistakes of Small and about 4x faster.",
            kind="parakeet",
            folder="sherpa-onnx-nemo-parakeet-unified-en-0.6b-int8-non-streaming",
            archive="sherpa-onnx-nemo-parakeet-unified-en-0.6b-int8-non-streaming.tar.bz2",
            archive_bytes=501_350_460,
            sha256="99f63605b3a85a54c250c0869670a687b7d6598a47bf2421515e1f839a76e150",
            download_mb=478,
            languages=("en",),
            files=("encoder.int8.onnx", "decoder.int8.onnx", "joiner.int8.onnx", "tokens.txt"),
        ),
        SherpaModel(
            id="parakeet-v3",
            label="Parakeet v3, European languages",
            description="Fast: English and 24 other European languages (German, French...).",
            kind="parakeet",
            folder="sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8",
            archive="sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2",
            archive_bytes=487_170_055,
            sha256="5793d0fd397c5778d2cf2126994d58e9d56b1be7c04d13c7a15bb1b4eafb16bf",
            download_mb=464,
            languages=_PARAKEET_V3_LANGUAGES,
            files=("encoder.int8.onnx", "decoder.int8.onnx", "joiner.int8.onnx", "tokens.txt"),
        ),
        SherpaModel(
            id="cohere-14",
            label="Cohere Transcribe, Arabic and 13 languages",
            description="Best Arabic: keeps Egyptian dialect, which Whisper rewrites.",
            kind="cohere",
            folder="sherpa-onnx-cohere-transcribe-14-lang-int8-2026-04-01",
            archive="sherpa-onnx-cohere-transcribe-14-lang-int8-2026-04-01.tar.bz2",
            archive_bytes=1_699_791_751,
            sha256="bd582588d50685a795dcd2807ab77e11361b8312d96c53884682def45ab4206d",
            download_mb=1621,
            languages=_COHERE_LANGUAGES,
            files=(
                "encoder.int8.onnx",
                "encoder.int8.onnx.data",
                "decoder.int8.onnx",
                "tokens.txt",
            ),
        ),
        SherpaModel(
            id="moonshine-ar",
            label="Moonshine Arabic, small and fast",
            description="Arabic about as accurate as Small, 8x faster, a quarter of the size.",
            kind="moonshine_v2",
            folder="sherpa-onnx-moonshine-base-ar-quantized-2026-02-27",
            archive="sherpa-onnx-moonshine-base-ar-quantized-2026-02-27.tar.bz2",
            archive_bytes=119_143_068,
            sha256="4d3f16fe354d8536d3323d3eaf4c12fafb1976b5dc0a12862ab25934da94285b",
            download_mb=114,
            languages=("ar",),
            files=("encoder_model.ort", "decoder_model_merged.ort", "tokens.txt"),
        ),
    )
}

# Which downloaded model "Automatic" prefers for a dictation language, best first.
_AUTO_PREFERENCE: dict[str, tuple[str, ...]] = {
    "ar": ("cohere-14", "moonshine-ar"),
    "en": ("parakeet-unified-en", "parakeet-v3"),
    **{code: ("parakeet-v3",) for code in _PARAKEET_V3_LANGUAGES if code != "en"},
}


def is_ready(model: SherpaModel) -> bool:
    return all((model.path / name).is_file() for name in model.files)


def downloaded_ids() -> list[str]:
    return [model_id for model_id, model in MODELS.items() if is_ready(model)]


def remove(model: SherpaModel) -> None:
    shutil.rmtree(model.path, ignore_errors=True)


def _download_archive(
    model: SherpaModel, dest: Path, progress: Callable[[str], None] | None
) -> None:
    """Streams the archive to `dest` (never held in memory) and checks it."""
    request = urllib.request.Request(model.url, headers={"User-Agent": "VoxScribe"})
    digest = hashlib.sha256()
    received = 0
    with urllib.request.urlopen(request, timeout=30) as response, dest.open("wb") as out:  # noqa: S310 -- fixed github URL
        while chunk := response.read(1024 * 1024):
            out.write(chunk)
            digest.update(chunk)
            received += len(chunk)
            if progress:
                progress(f"Downloading {model.label}... {received * 100 // model.archive_bytes}%")
    if received != model.archive_bytes:
        raise OSError(f"The {model.label} download was incomplete. Try again.")
    if digest.hexdigest() != model.sha256:
        raise OSError(f"The {model.label} download did not match its checksum. Try again.")


def download(model: SherpaModel, progress: Callable[[str], None] | None = None) -> None:
    """Fetches and unpacks one model into MODELS_DIR. Raises OSError when the
    network is unavailable (including when offline mode is on), the download is
    cut short or fails its checksum."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="voxscribe-model-", dir=MODELS_DIR) as tmp:
        archive = Path(tmp) / model.archive
        _download_archive(model, archive, progress)
        if progress:
            progress(f"Unpacking {model.label}... this takes a minute")
        # Unpack beside the final folder first, so an interrupted unpack never
        # leaves a half-installed model that looks complete.
        staging = Path(tmp) / "unpacked"
        with tarfile.open(archive, mode="r:bz2") as tar:
            tar.extractall(staging, filter="data")  # noqa: S202 -- fixed archive, data filter
        source = staging / model.folder
        if not source.is_dir():
            raise OSError(f"The {model.label} archive had an unexpected layout.")
        remove(model)
        shutil.move(str(source), str(model.path))
    if not is_ready(model):
        raise OSError(f"The {model.label} files are incomplete. Try again.")


def _build_recognizer(model: SherpaModel):  # noqa: ANN202 -- sherpa_onnx is imported lazily
    import sherpa_onnx  # heavy import, only needed once a model is used

    threads = max(1, min(4, os.cpu_count() or 1))
    folder = model.path
    recognizer = sherpa_onnx.OfflineRecognizer
    if model.kind == "parakeet":
        return recognizer.from_transducer(
            encoder=str(folder / "encoder.int8.onnx"),
            decoder=str(folder / "decoder.int8.onnx"),
            joiner=str(folder / "joiner.int8.onnx"),
            tokens=str(folder / "tokens.txt"),
            num_threads=threads,
            model_type="nemo_transducer",
        )
    if model.kind == "cohere":
        return recognizer.from_cohere_transcribe(
            encoder=str(folder / "encoder.int8.onnx"),
            decoder=str(folder / "decoder.int8.onnx"),
            tokens=str(folder / "tokens.txt"),
            num_threads=threads,
            language="en",
        )
    if model.kind == "moonshine_v2":
        return recognizer.from_moonshine_v2(
            encoder=str(folder / "encoder_model.ort"),
            decoder=str(folder / "decoder_model_merged.ort"),
            tokens=str(folder / "tokens.txt"),
            num_threads=threads,
        )
    raise ValueError(f"Unknown model kind {model.kind}")


class SherpaTranscriber:
    """One extra model, loaded. `transcribe` mirrors `Transcriber.transcribe`
    for live dictation; it is not used for files (they need timestamps)."""

    device = "cpu"

    def __init__(self, model: SherpaModel, recognizer=None) -> None:  # noqa: ANN001
        self.model = model
        self._recognizer = recognizer if recognizer is not None else _build_recognizer(model)
        self._lock = threading.Lock()
        # (word, score) of the last dictation, for the unsure-word marks. Empty for a
        # model that does not report how sure it was (Cohere, Moonshine).
        self.last_words: list[tuple[str, float]] = []

    def transcribe(self, audio: np.ndarray, language: str | None = "en") -> str:
        if len(audio) == 0 or not looks_like_speech(audio):
            return ""
        peak = float(np.max(np.abs(audio)))
        if peak < 0.5:
            audio = audio * (0.5 / peak)
        with self._lock:
            stream = self._recognizer.create_stream()
            if self.model.kind == "cohere":
                spoken = language if language in self.model.languages else "en"
                stream.set_option("language", spoken)
            stream.accept_waveform(16_000, audio.astype(np.float32))
            self._recognizer.decode_stream(stream)
            result = stream.result
            try:
                self.last_words = unsure.words_with_confidence(
                    list(result.tokens), list(result.ys_log_probs)
                )
            except (AttributeError, TypeError):
                self.last_words = []
            return result.text.strip()


class SpeechRouter:
    """Looks like a `Transcriber` and sends each dictation to the best model.

    `mode` is "auto" (best downloaded model for the dictation language) or the
    id of one model. Whisper answers whenever the choice is not clear: language
    auto-detect, translation, a language the model lacks, a model that is not
    downloaded, or any error (after which that model is skipped for this run).
    """

    def __init__(  # noqa: ANN204
        self,
        whisper,  # noqa: ANN001
        mode: str,
        loader: Callable[[SherpaModel], SherpaTranscriber] = SherpaTranscriber,
    ):
        self.whisper = whisper
        self.mode = mode
        self._loader = loader
        self._loaded: SherpaTranscriber | None = None  # one extra model in memory at a time
        self._failed: set[str] = set()
        self._lock = threading.Lock()
        self._last_words: list[tuple[str, float]] = []
        self._unsure_below = unsure.UNSURE_BELOW

    @property
    def device(self) -> str:
        return self.whisper.device

    @property
    def collect_confidence(self) -> bool:
        return getattr(self.whisper, "collect_confidence", False)

    @collect_confidence.setter
    def collect_confidence(self, value: bool) -> None:
        self.whisper.collect_confidence = value

    @property
    def last_words(self) -> list[tuple[str, float]]:
        """(word, score) pairs of the last dictation. Empty when the model that did
        the work does not report how sure it was."""
        return self._last_words

    @property
    def unsure_below(self) -> float:
        """Scores under this mean unsure, for the model that did the last dictation."""
        return self._unsure_below

    def pick(self, language: str | None, task: str = "transcribe") -> SherpaModel | None:
        """The extra model to use for this dictation, or None for Whisper."""
        if language is None or task == "translate":
            return None
        if self.mode == SPEECH_ENGINE_AUTO:
            ids = _AUTO_PREFERENCE.get(language, ())
        else:
            ids = (self.mode,)
        for model_id in ids:
            model = MODELS.get(model_id)
            if (
                model is not None
                and language in model.languages
                and model_id not in self._failed
                and is_ready(model)
            ):
                return model
        return None

    def _engine(self, model: SherpaModel) -> SherpaTranscriber:
        with self._lock:
            if self._loaded is None or self._loaded.model.id != model.id:
                self._loaded = None  # free the old one before loading the next
                self._loaded = self._loader(model)
            return self._loaded

    def warm(self, language: str | None) -> None:
        """Loads the model for `language` ahead of the first dictation."""
        model = self.pick(language)
        if model is not None:
            try:
                self._engine(model)
            except Exception:  # noqa: BLE001 -- the first dictation falls back to Whisper
                self._failed.add(model.id)

    def transcribe(
        self,
        audio: np.ndarray,
        language: str | None = "en",
        initial_prompt: str | None = None,
        task: str = "transcribe",
        beam_size: int = 1,
    ) -> str:
        self._last_words = []
        self._unsure_below = unsure.UNSURE_BELOW
        model = self.pick(language, task)
        if model is not None:
            try:
                engine = self._engine(model)
                text = engine.transcribe(audio, language)
                self._last_words = list(getattr(engine, "last_words", []))
                self._unsure_below = unsure.SHERPA_UNSURE_BELOW
                return text
            except Exception:  # noqa: BLE001
                self._failed.add(model.id)
        text = self.whisper.transcribe(
            audio, language=language, initial_prompt=initial_prompt, task=task, beam_size=beam_size
        )
        self._last_words = list(getattr(self.whisper, "last_words", []))
        return text

    # Files need segment timestamps, which only Whisper gives here.
    def transcribe_file(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        return self.whisper.transcribe_file(*args, **kwargs)

    def transcribe_file_segments(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        return self.whisper.transcribe_file_segments(*args, **kwargs)

    def transcribe_file_detailed(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        return self.whisper.transcribe_file_detailed(*args, **kwargs)
