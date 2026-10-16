import pytest

import cli

DETAILED = [
    (0.0, 1.5, " um so the meeting is at noon", [(0.2, 0.5, "so"), (0.6, 1.4, "noon")]),
    (2.0, 3.0, " ", []),
    (3.0, 4.0, " thanks everyone", [(3.1, 3.5, "thanks"), (3.5, 3.9, "everyone")]),
]


def test_defaults_are_plain_text_to_stdout():
    args = cli.build_parser().parse_args(["a.mp3"])
    assert (args.format, args.output, args.model, args.language) == ("txt", None, None, "en")
    assert not args.translate and not args.raw


def test_an_unknown_model_is_refused_by_the_parser():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["a.mp3", "--model", "huge"])


@pytest.mark.parametrize(
    ("fmt", "model", "translate", "pro", "allowed"),
    [
        ("txt", "small", False, False, True),
        ("srt", "base", True, False, True),
        ("vtt", "small", False, False, False),
        ("md", "small", False, True, True),
        ("txt", "medium", False, False, False),
        ("txt", "large", False, True, True),
        ("txt", "large-v3-turbo", True, True, False),
    ],
)
def test_the_same_free_and_pro_line_as_the_app(fmt, model, translate, pro, allowed):
    assert (cli.check_allowed(fmt, model, translate, pro) is None) == allowed


def test_plain_text_is_cleaned_like_dictation(monkeypatch):
    monkeypatch.setattr(cli, "apply_replacements", lambda text: text.replace("noon", "12:00"))
    text = cli.render("txt", DETAILED, "meeting")
    assert "um" not in text.split()
    assert "12:00" in text
    assert text.endswith("\n")


def test_raw_text_is_exactly_what_was_heard():
    assert cli.render("txt", DETAILED, "meeting", raw=True) == (
        "um so the meeting is at noon thanks everyone\n"
    )


def test_nothing_heard_prints_nothing():
    assert cli.render("txt", [(0.0, 1.0, " ", [])], "x") == ""


def test_srt_and_vtt_are_captions():
    srt = cli.render("srt", DETAILED, "meeting")
    assert srt.startswith("1\n00:00:00,")
    assert "-->" in srt
    assert cli.render("vtt", DETAILED, "meeting").startswith("WEBVTT")


def test_markdown_has_the_title():
    assert "meeting" in cli.render("md", DETAILED, "meeting")


def test_an_existing_file_is_never_replaced(tmp_path):
    first = cli.output_path(tmp_path, r"C:\media\talk.mp4", "srt")
    assert first == tmp_path / "talk.srt"
    first.write_text("hand corrected", encoding="utf-8")
    assert cli.output_path(tmp_path, r"C:\media\talk.mp4", "srt") == tmp_path / "talk (2).srt"


def test_a_pro_format_without_pro_stops_before_loading_anything(monkeypatch, capsys):
    monkeypatch.setattr(cli.voxscribe_license, "is_pro", lambda: False)
    assert cli.main(["a.mp3", "--format", "vtt", "--model", "small"]) == 2
    assert "needs VoxScribe Pro" in capsys.readouterr().err


def test_no_media_files_is_an_error(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli.voxscribe_license, "is_pro", lambda: False)
    (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
    assert cli.main([str(tmp_path / "notes.txt"), "--model", "small"]) == 2
    assert "No audio or video files" in capsys.readouterr().err
