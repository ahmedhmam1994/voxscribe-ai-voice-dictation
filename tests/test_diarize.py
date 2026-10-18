"""Tests for core/diarize.py's pure parts: matching speakers to transcript
segments and naming them. The models themselves are not run here."""

import core.diarize as diarize
from core.diarize import SpeakerTurn, assign_speakers, label_segments

SEGMENTS = [
    (0.0, 3.0, "Hello there."),
    (3.0, 6.0, "Hi, how are you?"),
    (6.0, 9.0, "Fine, thanks."),
]
TURNS = [SpeakerTurn(0.0, 3.2, 1), SpeakerTurn(3.2, 6.1, 0), SpeakerTurn(6.1, 9.0, 1)]


def test_each_segment_takes_the_speaker_it_overlaps_most():
    assert assign_speakers(SEGMENTS, TURNS) == [1, 0, 1]


def test_a_segment_straddling_two_turns_goes_to_the_longer_overlap():
    segments = [(2.0, 6.0, "long")]
    turns = [SpeakerTurn(0.0, 3.0, 0), SpeakerTurn(3.0, 8.0, 1)]

    assert assign_speakers(segments, turns) == [1]


def test_a_segment_with_no_turn_takes_the_previous_speaker():
    turns = [SpeakerTurn(0.0, 3.0, 2)]

    assert assign_speakers(SEGMENTS, turns) == [2, 2, 2]


def test_nothing_known_yet_gives_none():
    assert assign_speakers(SEGMENTS, []) == [None, None, None]


def test_speakers_are_numbered_in_order_of_first_appearance():
    labelled = label_segments(SEGMENTS, TURNS)

    assert [text for _s, _e, text in labelled] == [
        "Speaker 1: Hello there.",
        "Speaker 2: Hi, how are you?",
        "Speaker 1: Fine, thanks.",
    ]


def test_names_replace_the_numbers_and_blank_names_keep_the_default():
    labelled = label_segments(SEGMENTS, TURNS, names=["Sam", " "])

    assert [text.split(":")[0] for _s, _e, text in labelled] == ["Sam", "Speaker 2", "Sam"]


def test_timestamps_and_unlabelled_segments_are_kept():
    labelled = label_segments([(0.0, 1.0, "a"), (1.0, 2.0, "  ")], [SpeakerTurn(0.0, 2.0, 0)])

    assert labelled[0][:2] == (0.0, 1.0)
    assert labelled[1] == (1.0, 2.0, "  ")


def test_models_ready_needs_both_files(monkeypatch, tmp_path):
    seg = tmp_path / "seg" / "model.onnx"
    emb = tmp_path / "emb.onnx"
    monkeypatch.setattr(diarize, "SEGMENTATION_MODEL", seg)
    monkeypatch.setattr(diarize, "EMBEDDING_MODEL", emb)
    assert not diarize.models_ready()

    seg.parent.mkdir()
    seg.write_bytes(b"x")
    assert not diarize.models_ready()

    emb.write_bytes(b"x")
    assert diarize.models_ready()


class _Resp:
    def __init__(self, data):
        self._data = [data]

    def read(self, _n=-1):
        return self._data.pop() if self._data else b""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_download_checks_size_and_checksum(monkeypatch):
    import hashlib
    import urllib.request

    import pytest

    from core import diarize

    data = b"model bytes"
    good = hashlib.sha256(data).hexdigest()
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Resp(data))
    assert diarize._download("https://example.invalid/m", len(data), good, None) == data

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Resp(data))
    with pytest.raises(OSError, match="checksum"):
        diarize._download("https://example.invalid/m", len(data), "0" * 64, None)

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Resp(data[:3]))
    with pytest.raises(OSError, match="incomplete"):
        diarize._download("https://example.invalid/m", len(data), good, None)


def test_pinned_checksums_match_the_published_files():
    from core import diarize

    assert len(diarize._SEGMENTATION_ARCHIVE_SHA256) == 64
    assert len(diarize._EMBEDDING_SHA256) == 64
