"""Tests for core/summarize.py (instant, model free summaries)."""

import time

from core import summarize as sm

MEETING = """We met to plan the clinic's new booking system.
The booking system must let patients pick a time online.
Sarah said the old phone booking takes too long for patients.
The weather was nice today.
We decided to use the online booking system from January.
Patients will get a reminder text the day before the booking.
I will send the booking system contract to Tom by Friday.
Tom asked whether the booking system works on phones?
My cat likes the sofa.
The online booking system also cuts phone calls for the front desk."""


def test_key_sentences_are_about_the_main_topic_and_keep_their_order():
    result = sm.summarize(MEETING, "short")
    assert 2 <= len(result.points) <= 3
    assert all("booking" in p.lower() for p in result.points)
    positions = [MEETING.index(p) for p in result.points]
    assert positions == sorted(positions)


def test_off_topic_sentences_are_left_out():
    points = " ".join(sm.summarize(MEETING, "medium").points)
    assert "cat" not in points and "weather" not in points


def test_action_items_are_found():
    actions = sm.summarize(MEETING).actions
    assert any("send the booking system contract" in a for a in actions)
    assert not any(a.endswith("?") for a in actions)


def test_medium_is_longer_than_short():
    text = " ".join(f"The project report number {i} covers budget and staff plans." for i in range(40))
    medium = sm.summarize(text, "medium").points
    assert len(medium) > len(sm.summarize(text, "short").points)


def test_too_short_text_gives_nothing():
    result = sm.summarize("Hello there my friend. How are you today?")
    assert result.is_empty()
    assert result.sentence_count == 2


def test_empty_text():
    assert sm.summarize("").is_empty()
    assert sm.summarize("   \n  ").is_empty()


def test_app_lines_are_not_treated_as_speech():
    text = (
        MEETING
        + "\nDownloaded to C:\\Users\\x\\Documents\\VoxScribe Links\\a.mp3"
        + "\n[error] boom happened here"
    )
    joined = " ".join(sm.sentences(text))
    assert "Downloaded" not in joined and "[error]" not in joined


def test_file_transcripts_as_the_app_shows_them_are_summarised():
    # Each file's text arrives on one line after its "[name]" label.
    text = (
        "Downloaded to C:\\Users\\x\\Documents\\VoxScribe Links\\clinic.m4a\n"
        "[clinic.m4a] " + MEETING.replace("\n", " ") + "\n"
        "  saved: clinic.srt\n"
        "[broken.mp3] [error] could not decode the file\n"
        "[quiet.wav] [no speech recognized]\n"
        "[Talk [id]] (the site's own captions, may contain mistakes) The booking system "
        "starts in January for every patient.\n"
    )
    found = sm.sentences(text)
    assert found[0] == "We met to plan the clinic's new booking system."
    assert any(s.startswith("The booking system starts in January") for s in found)
    joined = " ".join(found)
    assert "[" not in joined and "Downloaded" not in joined and "saved" not in joined
    assert "decode" not in joined and "site's own captions" not in joined
    assert not sm.summarize(text).is_empty()


def test_arabic_text_is_split_and_summarised():
    text = (
        "نريد نظام حجز جديد للعيادة. نظام الحجز يجب أن يعمل على الهاتف. "
        "الطقس جميل اليوم. هل نظام الحجز مجاني للمرضى؟ "
        "سنبدأ نظام الحجز في يناير. القطة نائمة على الكنبة."
    )
    result = sm.summarize(text)
    assert result.points
    assert all("الحجز" in p for p in result.points)


def test_text_output_has_both_sections():
    out = sm.summarize(MEETING).as_text()
    assert out.startswith("Summary\n- ")
    assert "\n\nAction items\n- " in out
    assert "\u2014" not in out and "\u2013" not in out


def test_a_long_meeting_is_fast():
    words = ["budget", "staff", "report", "patients", "clinic", "booking", "software", "training"]
    text = " ".join(
        f"Item {i} is about {words[i % 8]} and {words[(i * 3) % 8]} for team {i % 17}."
        for i in range(1500)
    )
    start = time.perf_counter()
    result = sm.summarize(text, "medium")
    assert time.perf_counter() - start < 5
    assert len(result.points) == sm.MAX_POINTS


def test_point_count_limits():
    assert sm.point_count(4, "short") == sm.MIN_POINTS
    assert sm.point_count(1000, "medium") == sm.MAX_POINTS
