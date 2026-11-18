import numpy as np

from core import hands_free as hf

SPEECH = np.full(hf.FRAME_SIZE, 0.5, dtype=np.float32)
QUIET = np.zeros(hf.FRAME_SIZE, dtype=np.float32)


def feed(seg: hf.Segmenter, pattern: list[tuple[np.ndarray, float]]) -> list[tuple]:
    events = []
    for frame, seconds in pattern:
        for _ in range(round(seconds / hf.FRAME_SEC)):
            events.extend(seg.push(frame))
    return events


def loud(frame: np.ndarray) -> bool:
    return bool(frame[0] > 0.1)


def phrases(events: list[tuple]) -> list[tuple]:
    return [e for e in events if e[0] == "phrase"]


def test_a_phrase_is_cut_at_a_pause():
    seg = hf.Segmenter(loud)
    events = feed(seg, [(QUIET, 1), (SPEECH, 2), (QUIET, 1.5)])
    assert events[0] == ("start",)
    (phrase,) = phrases(events)
    assert abs(phrase[2] - 2) < 0.1  # seconds of speech
    # Lead-in before the speech is kept, most of the pause after it is not.
    assert 2.2 < len(phrase[1]) / hf.SAMPLE_RATE < 2.8


def test_a_short_breath_inside_a_sentence_does_not_cut_it():
    seg = hf.Segmenter(loud)
    events = feed(seg, [(SPEECH, 1), (QUIET, 0.6), (SPEECH, 1), (QUIET, 1.5)])
    assert len(phrases(events)) == 1


def test_two_sentences_with_a_real_pause_are_two_phrases():
    seg = hf.Segmenter(loud)
    events = feed(seg, [(SPEECH, 1), (QUIET, 2), (SPEECH, 1), (QUIET, 2)])
    assert len(phrases(events)) == 2


def test_a_click_does_not_start_a_phrase():
    seg = hf.Segmenter(loud)
    assert feed(seg, [(QUIET, 1), (SPEECH, 0.064), (QUIET, 2)]) == []


def test_a_very_short_sound_is_dropped():
    seg = hf.Segmenter(loud, min_phrase_sec=0.3)
    events = feed(seg, [(SPEECH, 0.2), (QUIET, 2)])
    assert phrases(events) == []


def test_a_long_run_is_cut_without_a_pause():
    seg = hf.Segmenter(loud, max_phrase_sec=5)
    events = feed(seg, [(SPEECH, 12)])
    assert len(phrases(events)) == 2


def test_flush_types_what_is_still_being_said():
    seg = hf.Segmenter(loud)
    feed(seg, [(SPEECH, 1)])
    assert len(phrases(seg.flush())) == 1
    assert seg.flush() == []


def test_long_silence_ends_the_session_once():
    seg = hf.Segmenter(loud, idle_stop_sec=3)
    events = feed(seg, [(QUIET, 7)])
    assert events == [("idle",)]


def test_speech_resets_the_idle_clock():
    seg = hf.Segmenter(loud, idle_stop_sec=3)
    events = feed(seg, [(QUIET, 2), (SPEECH, 1), (QUIET, 2.5)])
    assert ("idle",) not in events


def test_resampler_turns_48k_into_16k_frames():
    r = hf.Resampler(48_000)
    frames = []
    for _ in range(10):
        frames += r.frames(np.ones(4800, dtype=np.float32))
    assert all(len(f) == hf.FRAME_SIZE for f in frames)
    assert len(frames) == 16_000 // hf.FRAME_SIZE  # one second in, nothing lost but the tail
    assert np.allclose(frames[0], 1.0)


def test_resampler_handles_odd_rates_and_16k():
    for rate in (44_100, 16_000, 22_050):
        r = hf.Resampler(rate)
        total = sum(len(f) for _ in range(20) for f in r.frames(np.zeros(rate // 20)))
        assert abs(total - 16_000) <= hf.FRAME_SIZE


def test_phantom_lines_are_dropped_but_real_speech_is_not():
    for text in ("Thanks for watching!", "Thank you for watching. Bye.", "Bye. Bye. Bye.",
                 "MMMMMMMMMM", "Hmm.", "you", "", "  "):
        assert hf.is_phantom(text), text
    for text in ("Thank you.", "Thanks for the report.", "Bye for now, see you Monday.",
                 "I watched it twice.", "Hmm, let me think about the price."):
        assert not hf.is_phantom(text), text


def test_stop_listening_is_heard_even_when_the_first_word_is_lost():
    for text in ("Stop listening.", "listening", "Tub listening", "Please stop listening"):
        assert hf.is_stop_command(text), text
    for text in ("I was not listening to the call.", "Listening is hard.", "Stop."):
        assert not hf.is_stop_command(text), text


def test_context_prompt_keeps_the_words_and_the_end_of_what_was_typed():
    typed = ["word " * 100]
    prompt = hf.context_prompt("Kowalczyk, LoRA.", typed)
    assert prompt.startswith("Kowalczyk, LoRA. ")
    assert len(prompt) <= len("Kowalczyk, LoRA. ") + hf.CONTEXT_CHARS
    assert hf.context_prompt(None, []) is None
    assert hf.context_prompt(None, ["Hello there."]) == "Hello there."


def test_match_command_fixes_misheard_commands():
    assert hf.match_command("New online.") == "new line"
    assert hf.match_command("ScratchZ.") == "scratch that"
    assert hf.match_command("Scratch that.") == "scratch that"
    assert hf.match_command("Send it!") == "send it"
    assert hf.match_command("New paragraph") == "new paragraph"


def test_match_command_leaves_real_phrases_alone():
    for text in ("Hello, how are you?", "Thank you.", "See you soon.", "Yes.", "Okay.",
                 "I will send the slides tonight.", "Sounds good to me."):
        assert hf.match_command(text) is None, text


def test_looks_unfinished():
    assert hf.looks_unfinished("I think we should...")
    assert hf.looks_unfinished("I think we should")
    assert hf.looks_unfinished("Let's go to the")
    assert hf.looks_unfinished("First, the numbers,")
    assert hf.looks_unfinished("We need to talk and.")
    assert not hf.looks_unfinished("The numbers look fine to me.")
    assert not hf.looks_unfinished("How are you?")
    assert not hf.looks_unfinished("")
    assert not hf.looks_unfinished("Thank you.")
    assert not hf.looks_unfinished("Can you send it?")
