import wave

import numpy as np

from core import meeting
from core.meeting import OTHERS, YOU, Line, merge_tracks, transcribe_meeting, wav_rms


def _wav(path, seconds, amplitude, rate=16_000):
    t = np.arange(int(seconds * rate)) / rate
    pcm = (amplitude * np.sin(2 * np.pi * 300 * t) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


def test_lines_are_merged_in_time_order_with_speakers():
    you = [(5.0, 7.0, "I agree with that.")]
    others = [(0.0, 3.0, "Can we move the launch?"), (9.0, 11.0, "Great, thanks.")]
    lines = merge_tracks(you, others)
    assert [(line.speaker, line.text) for line in lines] == [
        (OTHERS, "Can we move the launch?"),
        (YOU, "I agree with that."),
        (OTHERS, "Great, thanks."),
    ]


def test_short_gaps_between_the_same_speaker_are_joined():
    others = [(0.0, 2.0, "First part."), (3.0, 5.0, "Second part."), (12.0, 14.0, "Later.")]
    lines = merge_tracks([], others)
    assert [(line.start, line.end, line.text) for line in lines] == [
        (0.0, 5.0, "First part. Second part."),
        (12.0, 14.0, "Later."),
    ]


def test_a_microphone_line_that_repeats_the_others_is_echo():
    others = [(10.0, 14.0, "The quarterly report is due on Friday")]
    you = [(10.2, 14.1, "the quarterly report is due on Friday")]
    assert merge_tracks(you, others) == [
        Line(10.0, 14.0, OTHERS, "The quarterly report is due on Friday")
    ]


def test_a_garbled_echo_is_still_caught_by_similarity():
    others = [(10.0, 14.0, "The quarterly report is due on Friday")]
    you = [(10.0, 14.0, "the quarterly report is scored by Friday")]
    assert [line.speaker for line in merge_tracks(you, others)] == [OTHERS]


def test_a_fragment_of_what_others_said_is_echo():
    others = [(0.0, 6.0, "Action item. Maria will send the invoice by Friday.")]
    you = [(0.9, 2.9, "Action item.")]
    assert [line.speaker for line in merge_tracks(you, others)] == [OTHERS]


def test_a_quiet_microphone_line_under_loud_playback_is_echo():
    others = [(0.0, 4.0, "Something loud was said")]
    you = [(1.0, 3.0, "totally unrelated words appeared")]
    quiet_you = lambda a, b: 0.004  # noqa: E731
    loud_others = lambda a, b: 0.2  # noqa: E731
    assert [line.speaker for line in merge_tracks(you, others, quiet_you, loud_others)] == [OTHERS]


def test_real_interruptions_with_different_words_are_kept():
    others = [(0.0, 4.0, "We need the budget approved by Monday")]
    you = [(2.0, 4.0, "Sorry, which budget do you mean?")]
    lines = merge_tracks(you, others)
    assert len(lines) == 2
    assert {line.speaker for line in lines} == {YOU, OTHERS}


def test_a_loud_microphone_line_is_not_called_echo():
    others = [(0.0, 4.0, "Something loud was said")]
    you = [(1.0, 3.0, "totally unrelated words appeared")]
    lines = merge_tracks(you, others, lambda a, b: 0.1, lambda a, b: 0.2)
    assert len(lines) == 2


def test_empty_text_is_dropped():
    assert merge_tracks([(0, 1, "  ")], [(1, 2, "")]) == []


def test_wav_rms_measures_a_stretch(tmp_path):
    loud = tmp_path / "a.wav"
    _wav(loud, 2.0, 0.5)
    assert wav_rms(loud, 0.0, 1.0) > 0.3
    assert wav_rms(loud, 5.0, 6.0) == 0.0
    assert wav_rms(tmp_path / "missing.wav", 0, 1) == 0.0


class FakeTranscriber:
    def __init__(self, by_name):
        self.by_name = by_name
        self.calls = []

    def transcribe_file_segments(self, path, language=None, initial_prompt=None, on_progress=None):
        self.calls.append((path, language, initial_prompt))
        if on_progress:
            on_progress(100)
        return self.by_name["others" if "others" in path else "you"]


def test_transcribe_meeting_merges_postprocesses_and_reports_progress(tmp_path):
    you_path, others_path = tmp_path / "x-you.wav", tmp_path / "x-others.wav"
    _wav(you_path, 6.0, 0.2)
    _wav(others_path, 6.0, 0.2)
    transcriber = FakeTranscriber(
        {"you": [(4.0, 5.0, "ok send it")], "others": [(0.0, 2.0, "please send the invoice")]}
    )
    progress = []
    lines = transcribe_meeting(
        transcriber, you_path, others_path, "en", "hint",
        postprocess=str.upper, on_progress=progress.append,
    )
    assert [(line.speaker, line.text) for line in lines] == [
        (OTHERS, "PLEASE SEND THE INVOICE"),
        (YOU, "OK SEND IT"),
    ]
    assert all(call[1:] == ("en", "hint") for call in transcriber.calls)
    assert progress[-1] == 1.0 and progress == sorted(progress)


def test_transcribe_meeting_with_the_microphone_only(tmp_path):
    you_path = tmp_path / "x-you.wav"
    _wav(you_path, 3.0, 0.2)
    transcriber = FakeTranscriber({"you": [(0.0, 2.0, "just me talking")]})
    lines = transcribe_meeting(transcriber, you_path, None, None)
    assert [(line.speaker, line.text) for line in lines] == [(YOU, "just me talking")]
    assert len(transcriber.calls) == 1
    assert meeting.YOU == "You"
