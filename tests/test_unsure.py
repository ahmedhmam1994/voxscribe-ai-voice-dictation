import numpy as np

from core import transcribe, unsure


def test_only_low_probability_words_of_enough_length_count():
    words = [("He", 0.2), (" started", 0.9), (" metoprolol,", 0.31), (" and", 0.4), (" Okafor.", 0.55)]
    assert unsure.unsure_words(words) == ["metoprolol", "okafor"]


def test_no_unsure_words_gives_no_markup():
    assert unsure.mark_html("all clear here", [], "#f0a54a") is None
    assert unsure.mark_html("all clear here", ["missing"], "#f0a54a") is None


def test_unsure_words_are_underlined_and_text_is_escaped():
    out = unsure.mark_html("Take <b>metoprolol</b>, then rest.", ["metoprolol"], "#f0a54a")
    assert out == (
        "Take &lt;b&gt;"
        '<span style="color:#f0a54a; text-decoration: underline;">metoprolol</span>'
        "&lt;/b&gt;, then rest."
    )


def test_marked_word_keeps_its_original_casing_and_neighbours():
    out = unsure.mark_html("Dr. Okafor said hello.", ["okafor"], "#f0a54a")
    assert out == (
        'Dr. <span style="color:#f0a54a; text-decoration: underline;">Okafor</span> said hello.'
    )


def test_newlines_become_line_breaks():
    out = unsure.mark_html("one\ntwo three", ["three"], "#f0a54a")
    assert out is not None and "<br>" in out


class _Word:
    def __init__(self, word, probability):
        self.word, self.probability = word, probability


class _Segment:
    def __init__(self, text, words):
        self.text, self.words = text, words


def _fake_model(seen):
    class Model:
        def transcribe(self, audio, **kwargs):
            seen.update(kwargs)
            segment = _Segment(" hello world", [_Word(" hello", 0.95), _Word(" world", 0.3)])
            return iter([segment]), object()

    return Model()


def _loud_audio():
    t = np.arange(16000) / 16000
    return (0.6 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


def test_confidence_is_collected_only_when_asked(monkeypatch):
    seen = {}
    monkeypatch.setattr(transcribe, "WhisperModel", lambda *a, **k: _fake_model(seen))
    monkeypatch.setattr(transcribe, "looks_like_speech", lambda audio: True)
    t = transcribe.Transcriber("small")
    assert t.transcribe(_loud_audio()) == "hello world"
    assert seen["word_timestamps"] is False
    assert t.last_words == []

    t.collect_confidence = True
    assert t.transcribe(_loud_audio()) == "hello world"
    assert seen["word_timestamps"] is True
    assert t.last_words == [(" hello", 0.95), (" world", 0.3)]
    assert unsure.unsure_words(t.last_words) == ["world"]


def test_tokens_are_joined_into_words_with_a_geometric_mean_score():
    import math

    tokens = [" My", " ord", "er", " num", "ber"]
    logs = [math.log(0.9), math.log(0.99), math.log(0.36), math.log(0.8), math.log(0.8)]
    words = unsure.words_with_confidence(tokens, logs)
    assert [w for w, _ in words] == ["My", "order", "number"]
    assert round(words[1][1], 2) == round(math.sqrt(0.99 * 0.36), 2)
    assert round(words[2][1], 2) == 0.8


def test_tokens_that_do_not_line_up_give_no_words():
    assert unsure.words_with_confidence([" a", " b"], [-0.1]) == []
    assert unsure.words_with_confidence([], []) == []


def test_parakeet_scores_use_a_higher_threshold():
    words = [("order", 0.77), ("Preya", 0.73), ("number", 0.95)]
    assert unsure.unsure_words(words) == []
    assert unsure.unsure_words(words, unsure.SHERPA_UNSURE_BELOW) == ["order", "preya"]
