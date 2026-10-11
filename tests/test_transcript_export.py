"""Tests for core/transcript_export.py: VTT, Markdown and Word output."""

import io
import zipfile

from core.transcript_export import format_docx, format_markdown, format_vtt

SEGMENTS = [(0.0, 2.5, "Hello there."), (3661.25, 3665.0, "Second  & <last> line."), (4.0, 5.0, "  ")]


def test_vtt_has_a_header_and_dotted_timestamps():
    vtt = format_vtt(SEGMENTS)

    assert vtt.startswith("WEBVTT\n\n")
    assert "00:00:00.000 --> 00:00:02.500\nHello there." in vtt
    assert "01:01:01.250 --> 01:01:05.000" in vtt


def test_empty_segments_are_skipped():
    assert format_vtt(SEGMENTS).count("-->") == 2
    assert format_markdown(SEGMENTS, "Talk").count("**[") == 2


def test_markdown_has_a_title_and_timestamped_lines():
    assert format_markdown(SEGMENTS, "Talk") == (
        "# Talk\n\n**[00:00:00]** Hello there.\n\n**[01:01:01]** Second  & <last> line.\n"
    )


def test_docx_is_a_valid_zip_with_escaped_text():
    data = format_docx(SEGMENTS, "My talk")

    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.testzip() is None
        assert {"[Content_Types].xml", "_rels/.rels", "word/document.xml"} <= set(archive.namelist())
        document = archive.read("word/document.xml").decode("utf-8")
    assert "My talk" in document
    assert "[00:00:00] Hello there." in document
    assert "&amp; &lt;last&gt;" in document
