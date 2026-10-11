"""Speaker labels for transcribed files -- a Pro feature (see core/license.py).

Two small ONNX models run on this PC (via sherpa-onnx): one finds where
people are speaking, the other fingerprints each voice so the same person gets
the same label. Their output is matched to the transcript segments, and the
exports then read "Speaker 1: ...", "Speaker 2: ..." (or the names the user
typed in Settings).

The models are downloaded once on first use, like the Whisper model, and
nothing about the audio is sent anywhere.

Known limits: people talking over each other can be mislabelled, and two very
similar voices can merge into one speaker. A fixed speaker count in Settings
helps when the automatic count is off.
"""

from __future__ import annotations

import io
import tarfile
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

MODEL_DIR = Path.home() / "AppData" / "Local" / "VoxScribe" / "models" / "diarization"

_RELEASES = "https://github.com/k2-fsa/sherpa-onnx/releases/download"
_SEGMENTATION_URL = (
    f"{_RELEASES}/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2"
)
_SEGMENTATION_ARCHIVE_BYTES = 6_958_444
_EMBEDDING_URL = (
    f"{_RELEASES}/speaker-recongition-models/"
    "3dspeaker_speech_campplus_sv_zh_en_16k-common_advanced.onnx"
)
_EMBEDDING_BYTES = 28_281_164

SEGMENTATION_MODEL = MODEL_DIR / "sherpa-onnx-pyannote-segmentation-3-0" / "model.onnx"
EMBEDDING_MODEL = MODEL_DIR / "campplus_zh_en_advanced.onnx"
APPROX_DOWNLOAD_MB = 35

SAMPLE_RATE = 16_000

# How different two voices must be to count as different people. Higher merges
# more; lower splits more.
DEFAULT_THRESHOLD = 0.8


@dataclass(frozen=True)
class SpeakerTurn:
    """One stretch of speech by one speaker. Speakers are numbered from 0."""

    start: float
    end: float
    speaker: int


def models_ready() -> bool:
    return SEGMENTATION_MODEL.is_file() and EMBEDDING_MODEL.is_file()


def _download(url: str, expected_bytes: int, progress: Callable[[str], None] | None) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "VoxScribe"})
    chunks = []
    received = 0
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 -- fixed github URL
        while chunk := response.read(256 * 1024):
            chunks.append(chunk)
            received += len(chunk)
            if progress:
                progress(f"Downloading speaker model... {received * 100 // expected_bytes}%")
    data = b"".join(chunks)
    if len(data) != expected_bytes:
        raise OSError("The speaker model download was incomplete. Try again.")
    return data


def download_models(progress: Callable[[str], None] | None = None) -> None:
    """Fetches the two models into MODEL_DIR. Raises OSError if the network is
    unavailable (including when offline mode is on) or the download is cut short."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    if not SEGMENTATION_MODEL.is_file():
        archive = _download(_SEGMENTATION_URL, _SEGMENTATION_ARCHIVE_BYTES, progress)
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:bz2") as tar:
            tar.extractall(MODEL_DIR, filter="data")  # noqa: S202 -- fixed archive, data filter
    if not EMBEDDING_MODEL.is_file():
        data = _download(_EMBEDDING_URL, _EMBEDDING_BYTES, progress)
        EMBEDDING_MODEL.write_bytes(data)


def _run(audio: np.ndarray, num_clusters: int, threshold: float) -> list[SpeakerTurn]:
    import sherpa_onnx  # heavy import, only needed here

    config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                model=str(SEGMENTATION_MODEL)
            ),
        ),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(EMBEDDING_MODEL)),
        clustering=sherpa_onnx.FastClusteringConfig(
            num_clusters=num_clusters, threshold=threshold
        ),
        min_duration_on=0.3,
        min_duration_off=0.5,
    )
    engine = sherpa_onnx.OfflineSpeakerDiarization(config)
    result = engine.process(audio.astype(np.float32)).sort_by_start_time()
    return [SpeakerTurn(r.start, r.end, r.speaker) for r in result]


def diarize(
    audio: np.ndarray, num_speakers: int = 0, threshold: float = DEFAULT_THRESHOLD
) -> list[SpeakerTurn]:
    """Who speaks when in 16 kHz mono float audio. `num_speakers` 0 means detect.

    Asking the library for exactly N speakers often returns N - 1, because it
    drops one very short cluster. When that happens, try once more with N + 1
    and keep whichever result has the speaker count closest to what was asked."""
    if num_speakers <= 0:
        return _run(audio, -1, threshold)
    turns = _run(audio, num_speakers, threshold)
    if len({t.speaker for t in turns}) < num_speakers:
        retry = _run(audio, num_speakers + 1, threshold)
        if abs(len({t.speaker for t in retry}) - num_speakers) < abs(
            len({t.speaker for t in turns}) - num_speakers
        ):
            return retry
    return turns


def assign_speakers(
    segments: list[tuple[float, float, str]], turns: list[SpeakerTurn]
) -> list[int | None]:
    """The speaker for each transcript segment: whoever overlaps it the most.
    A segment no turn overlaps takes the previous segment's speaker, or None
    if there is none yet."""
    speakers: list[int | None] = []
    for start, end, _text in segments:
        overlap: dict[int, float] = {}
        for turn in turns:
            shared = min(end, turn.end) - max(start, turn.start)
            if shared > 0:
                overlap[turn.speaker] = overlap.get(turn.speaker, 0.0) + shared
        if overlap:
            speakers.append(max(overlap, key=lambda s: overlap[s]))
        else:
            speakers.append(speakers[-1] if speakers else None)
    return speakers


def label_segments(
    segments: list[tuple[float, float, str]],
    turns: list[SpeakerTurn],
    names: list[str] | None = None,
) -> list[tuple[float, float, str]]:
    """Prefixes each segment with its speaker, as "Speaker 1: text". Speakers are
    numbered in order of first appearance. `names` replaces "Speaker 1", "Speaker
    2" ... in that same order; blank entries keep the default."""
    order: dict[int, int] = {}
    labelled = []
    for (start, end, text), speaker in zip(segments, assign_speakers(segments, turns), strict=True):
        if speaker is None or not text.strip():
            labelled.append((start, end, text))
            continue
        number = order.setdefault(speaker, len(order) + 1)
        custom = names[number - 1].strip() if names and number <= len(names) else ""
        labelled.append((start, end, f"{custom or f'Speaker {number}'}: {text.strip()}"))
    return labelled
