"""Tests for core/site_link.py. No network and no real helper: fakes stand in."""

import hashlib
import io
import json as _json
from pathlib import Path

import pytest

from core import link_import as li
from core import network_guard
from core import site_link as sl


@pytest.fixture(autouse=True)
def _guard(monkeypatch, tmp_path):
    monkeypatch.setattr(network_guard, "LOG_PATH", tmp_path / "net.jsonl")
    network_guard.set_blocking(False)
    yield
    network_guard.set_blocking(False)


@pytest.fixture
def helper(tmp_path) -> Path:
    path = tmp_path / "helpers" / sl.HELPER_NAME
    path.parent.mkdir()
    path.write_bytes(b"x" * (2 * 1024 * 1024))
    return path


class FakeProcess:
    """Writes the given file (if any) into the output folder from the args and
    prints the given lines, like the helper would."""

    def __init__(self, args, lines, make=None):
        self.args = args
        template = Path(args[args.index("--output") + 1])
        out_lines = list(lines)
        if make:
            target = template.parent / make
            target.write_bytes(b"audio")
            out_lines.append(f"VXPATH {target}")
        self.stdout = io.BytesIO("".join(line + "\n" for line in out_lines).encode())
        self.pid = 1
        self.killed = False

    def wait(self, timeout=None):
        return 0

    def poll(self):
        return 0

    def kill(self):
        self.killed = True


def popen_with(lines, make=None):
    made = []

    def popen(args):
        made.append(FakeProcess(args, lines, make))
        return made[-1]

    popen.made = made
    return popen


# -- which links go to the helper -------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=abc",
        "https://youtu.be/abc",
        "https://m.youtube.com/watch?v=abc",
        "https://music.youtube.com/watch?v=abc",
        "https://vimeo.com/123",
        "https://soundcloud.com/a/b",
    ],
)
def test_video_sites_are_recognised(url):
    assert sl.is_site(url)


@pytest.mark.parametrize(
    "url",
    ["https://example.com/a.mp3", "https://notyoutube.com/x", "https://youtube.com.evil.io/x"],
)
def test_other_links_are_not_sites(url):
    assert not sl.is_site(url)


def test_plan_says_when_the_helper_is_needed(tmp_path, helper):
    assert sl.plan_for("https://youtu.be/x", tmp_path / "none.exe").needs_helper
    assert not sl.plan_for("https://youtu.be/x", helper).needs_helper
    assert not sl.plan_for("https://example.com/a.mp3", tmp_path / "none.exe").site


# -- the command line ---------------------------------------------------------


def test_args_ask_for_audio_of_one_video_with_a_cap(tmp_path):
    args = sl.build_args(Path("h.exe"), "https://youtu.be/x", tmp_path, max_bytes=123)
    assert args[0] == "h.exe"
    assert "--no-playlist" in args and "--ignore-config" in args
    assert args[args.index("--format") + 1] == "bestaudio/best"
    assert args[args.index("--max-filesize") + 1] == "123"
    assert args[args.index("--match-filter") + 1] == "!is_live"
    # The link comes last, after "--", so a link can never be read as an option.
    assert args[-2:] == ["--", "https://youtu.be/x"]


def test_progress_and_path_lines_are_parsed():
    assert sl.parse_progress("VXPROG 100 400 NA") == (100, 400)
    assert sl.parse_progress("VXPROG 100 NA 900.5") == (100, 900)
    assert sl.parse_progress("VXPROG 100 NA NA") == (100, None)
    assert sl.parse_progress("VXPROG NA NA NA") is None
    assert sl.parse_progress("[download] 5%") is None
    assert sl.parse_path("VXPATH C:\\a b\\c.webm") == "C:\\a b\\c.webm"
    assert sl.parse_path("something else") is None


# -- downloading ---------------------------------------------------------------


def test_audio_is_saved_and_the_work_folder_removed(tmp_path, helper):
    out = tmp_path / "links"
    steps = []
    popen = popen_with(
        ["VXPROG 10 100 NA", "[info] hello", "VXPROG 100 100 NA"], make="Talk [id].webm"
    )
    path = sl.download_audio(
        "https://youtu.be/x",
        out,
        helper=helper,
        popen=popen,
        progress=lambda d, t: steps.append((d, t)),
    )
    assert path == out / "Talk [id].webm" and path.read_bytes() == b"audio"
    assert steps == [(10, 100), (100, 100)]
    assert [p.name for p in out.iterdir()] == ["Talk [id].webm"]


def test_existing_file_is_not_overwritten(tmp_path, helper):
    out = tmp_path / "links"
    out.mkdir()
    (out / "Talk.m4a").write_bytes(b"old")
    path = sl.download_audio(
        "https://youtu.be/x", out, helper=helper, popen=popen_with([], make="Talk.m4a")
    )
    assert path.name == "Talk (2).m4a"
    assert (out / "Talk.m4a").read_bytes() == b"old"


def test_helper_errors_become_plain_messages(tmp_path, helper):
    out = tmp_path / "links"
    with pytest.raises(sl.SiteError, match="private"):
        sl.download_audio(
            "https://youtu.be/x",
            out,
            helper=helper,
            popen=popen_with(
                ["ERROR: [youtube] x: Private video. Sign in if you've been granted access"]
            ),
        )
    assert list(out.iterdir()) == []


def test_skipped_video_without_a_file_is_reported(tmp_path, helper):
    lines = ["[download] File is larger than max-filesize (5 bytes > 1 bytes). Aborting."]
    with pytest.raises(sl.SiteError, match="2 GB"):
        sl.download_audio("https://youtu.be/x", tmp_path, helper=helper, popen=popen_with(lines))


def test_non_media_result_is_refused(tmp_path, helper):
    with pytest.raises(sl.SiteError, match="not audio"):
        sl.download_audio(
            "https://youtu.be/x", tmp_path / "o", helper=helper, popen=popen_with([], make="x.html")
        )
    assert list((tmp_path / "o").iterdir()) == []


def test_stop_request_cancels_and_cleans_up(tmp_path, helper):
    out = tmp_path / "links"
    popen = popen_with(["VXPROG 1 9 NA"] * 3, make="a.webm")
    with pytest.raises(li.Cancelled):
        sl.download_audio(
            "https://youtu.be/x", out, helper=helper, popen=popen, should_stop=lambda: True
        )
    assert list(out.iterdir()) == []


def test_missing_helper_is_reported_before_anything_runs(tmp_path):
    popen = popen_with([])
    with pytest.raises(sl.HelperMissing):
        sl.download_audio("https://youtu.be/x", tmp_path, helper=tmp_path / "no.exe", popen=popen)
    assert popen.made == []


def test_offline_mode_refuses_without_starting_the_helper(tmp_path, helper):
    network_guard.set_blocking(True)
    popen = popen_with([], make="a.webm")
    with pytest.raises(sl.SiteError, match="offline mode"):
        sl.download_audio("https://youtu.be/x", tmp_path, helper=helper, popen=popen)
    assert popen.made == []


def test_the_site_host_is_logged(tmp_path, helper):
    sl.download_audio(
        "https://www.youtube.com/watch?v=x",
        tmp_path,
        helper=helper,
        popen=popen_with([], make="a.webm"),
    )
    assert [c.host for c in network_guard.recent()] == ["www.youtube.com"]


def test_bad_links_are_refused(tmp_path, helper):
    with pytest.raises(sl.SiteError):
        sl.download_audio("file:///C:/x", tmp_path, helper=helper, popen=popen_with([]))


# -- error messages ------------------------------------------------------------


@pytest.mark.parametrize(
    ("output", "words", "update"),
    [
        ("ERROR: [youtube] x: Sign in to confirm you're not a bot", "not a bot", False),
        ("ERROR: [youtube] x: Sign in to confirm your age", "age restricted", False),
        (
            "ERROR: [youtube] x: The uploader has not made this video available in your country",
            "country",
            False,
        ),
        ("ERROR: [youtube] x: This video is unavailable", "not available", False),
        ("ERROR: Unsupported URL: https://example.com/page", "cannot read that site", False),
        (
            "ERROR: unable to download webpage: <urlopen error [Errno 11001] getaddrinfo failed>",
            "internet",
            False,
        ),
        ("ERROR: [youtube] x: HTTP Error 429: Too Many Requests", "limiting", False),
        ("[youtube] x: does not pass filter (!is_live), skipping", "Live streams", False),
        ("ERROR: [youtube] x: Unable to extract nsig function code", "update", True),
        ("ERROR: [youtube] x: Requested format is not available", "update", True),
        ("ERROR: something new and strange", "something new and strange", True),
    ],
)
def test_error_mapping(output, words, update):
    err = sl.friendly_site_error(output)
    assert words.lower() in str(err).lower()
    assert err.can_update is update
    assert "\u2014" not in str(err) and "\u2013" not in str(err)


# -- getting the helper --------------------------------------------------------


class Body:
    def __init__(self, data: bytes, length: bool = True):
        self._io = io.BytesIO(data)
        self.headers = {"Content-Length": str(len(data))} if length else {}

    def read(self, n=-1):
        return self._io.read(n)

    def close(self):
        pass


def fake_release(exe: bytes, listed_hash: str | None = None):
    digest = listed_hash or hashlib.sha256(exe).hexdigest()
    sums = f"{'0' * 64}  yt-dlp_linux\n{digest}  yt-dlp.exe\n{'1' * 64}  yt-dlp_x86.exe\n".encode()

    def opener(url):
        if url.endswith(sl.SUMS_NAME):
            return Body(sums)
        assert url.endswith(sl.HELPER_NAME)
        return Body(exe)

    return opener


def test_expected_hash_reads_the_right_line():
    text = f"{'a' * 64}  yt-dlp_x86.exe\n{'b' * 64}  yt-dlp.exe\n"
    assert sl.expected_hash(text) == "b" * 64
    assert sl.expected_hash("nothing here") is None


def test_helper_is_kept_only_when_the_checksum_matches(tmp_path):
    target = tmp_path / "h" / sl.HELPER_NAME
    exe = b"MZ" + b"\0" * 5000
    steps = []
    sl.install_helper(
        target=target, opener=fake_release(exe), progress=lambda d, t: steps.append(d)
    )
    assert target.read_bytes() == exe and steps[-1] == len(exe)


def test_helper_with_a_wrong_checksum_is_thrown_away(tmp_path):
    target = tmp_path / "h" / sl.HELPER_NAME
    with pytest.raises(sl.SiteError, match="checksum"):
        sl.install_helper(target=target, opener=fake_release(b"evil", "c" * 64))
    assert not target.exists()
    assert list(target.parent.iterdir()) == []


def test_update_replaces_the_old_helper(tmp_path):
    target = tmp_path / sl.HELPER_NAME
    target.write_bytes(b"old")
    sl.install_helper(target=target, opener=fake_release(b"new build"))
    assert target.read_bytes() == b"new build"


def test_missing_checksum_list_stops_the_install(tmp_path):
    def opener(url):
        return Body(b"not a sums file")

    with pytest.raises(sl.SiteError):
        sl.install_helper(target=tmp_path / sl.HELPER_NAME, opener=opener)


# -- the site's own captions ----------------------------------------------------

MANUAL_VTT = """WEBVTT
Kind: captions
Language: en

00:00:01.200 --> 00:00:03.360
All right, so here we are, in front of the
elephants

00:00:05.318 --> 00:00:07.974
the cool thing &amp; more

00:00:08.000 --> 00:00:09.000
[Music]
"""

# The rolling style of automatic captions: each card repeats the line above.
AUTO_VTT = """WEBVTT
Kind: captions
Language: en

00:00:00.199 --> 00:00:02.869 align:start position:0%

hello<00:00:00.480><c> everyone</c><00:00:00.880><c> and</c>

00:00:02.869 --> 00:00:02.879 align:start position:0%
hello everyone and


00:00:02.879 --> 00:00:05.470 align:start position:0%
hello everyone and
welcome<00:00:03.120><c> to</c><00:00:03.400><c> the</c><00:00:03.700><c> clinic</c>

00:00:05.470 --> 00:00:05.480 align:start position:0%
welcome to the clinic


00:00:05.480 --> 00:00:08.000 align:start position:0%
welcome to the clinic
today<c> we</c><c> talk</c>
"""


def test_manual_captions_are_parsed():
    segments = sl.parse_vtt(MANUAL_VTT)
    assert segments[0] == (1.2, 3.36, "All right, so here we are, in front of the elephants")
    assert segments[1][2] == "the cool thing & more"
    assert len(segments) == 2  # the [Music] card is dropped


def test_rolling_automatic_captions_appear_once():
    text = sl.captions_text(sl.parse_vtt(AUTO_VTT))
    assert text == "hello everyone and welcome to the clinic today we talk"


def test_hour_timestamps():
    segments = sl.parse_vtt("WEBVTT\n\n01:02:03.500 --> 01:02:04.000\nhi there\n")
    assert segments == [(3723.5, 3724.0, "hi there")]


def test_caption_languages_never_ask_for_translations():
    assert sl.caption_languages("ar") == "ar,ar-.*"
    assert sl.caption_languages(None) == "en,en-.*"
    # Automatic captions: only the track in the language actually spoken.
    assert sl.caption_languages("ar", automatic=True) == "ar-orig"
    assert sl.caption_languages(None, automatic=True) == ".*-orig"


def test_automatic_captions_are_tried_when_none_were_written(tmp_path, helper):
    made = []

    def popen(args):
        automatic = "--write-auto-subs" in args
        files = {"Talk [id].en-orig.vtt": AUTO_VTT} if automatic else {}
        made.append(CaptionProcess(args, files))
        return made[-1]

    result = sl.fetch_captions(
        "https://youtu.be/x", tmp_path / "o", "en", helper=helper, popen=popen
    )
    assert ["--write-auto-subs" in p.args for p in made] == [False, True]
    assert made[1].args[made[1].args.index("--sub-langs") + 1] == "en-orig"
    assert result.title == "Talk [id]" and result.text.startswith("hello everyone")


class CaptionProcess(FakeProcess):
    def __init__(self, args, files, lines=()):
        template = Path(args[args.index("--output") + 1])
        for name, body in files.items():
            (template.parent / name).write_text(body, encoding="utf-8")
        self.args = args
        self.stdout = io.BytesIO("".join(line + "\n" for line in lines).encode())
        self.pid = 1


def caption_popen(files, lines=()):
    made = []

    def popen(args):
        made.append(CaptionProcess(args, files, lines))
        return made[-1]

    popen.made = made
    return popen


def test_captions_are_fetched_without_downloading_media(tmp_path, helper):
    out = tmp_path / "links"
    popen = caption_popen({"Zoo [id].en-GB.vtt": AUTO_VTT, "Zoo [id].en.vtt": MANUAL_VTT})
    result = sl.fetch_captions("https://youtu.be/x", out, "en", helper=helper, popen=popen)
    args = popen.made[0].args
    assert "--skip-download" in args and "--format" not in args
    assert result.title == "Zoo [id]"
    assert result.text.startswith("All right")  # the exact language wins
    assert result.srt_path is None
    assert list(out.iterdir()) == []  # the work folder is gone


def test_captions_can_be_saved_as_srt(tmp_path, helper):
    out = tmp_path / "links"
    popen = caption_popen({"Zoo [id].en.vtt": MANUAL_VTT})
    result = sl.fetch_captions(
        "https://youtu.be/x", out, "en", save_srt=True, helper=helper, popen=popen
    )
    assert result.srt_path == out / "Zoo [id] (site captions).srt"
    assert result.srt_path.read_text(encoding="utf-8").startswith("1\n00:00:01,200 --> ")


def test_missing_captions_are_reported(tmp_path, helper):
    with pytest.raises(sl.NoCaptions, match="Arabic"):
        sl.fetch_captions(
            "https://youtu.be/x", tmp_path, "ar", helper=helper, popen=caption_popen({})
        )


def test_caption_errors_still_get_plain_messages(tmp_path, helper):
    popen = caption_popen({}, ["ERROR: [youtube] x: Private video"])
    with pytest.raises(sl.SiteError, match="private") as info:
        sl.fetch_captions("https://youtu.be/x", tmp_path, "en", helper=helper, popen=popen)
    assert not isinstance(info.value, sl.NoCaptions)


def test_captions_obey_offline_mode(tmp_path, helper):
    network_guard.set_blocking(True)
    popen = caption_popen({"a.en.vtt": MANUAL_VTT})
    with pytest.raises(sl.SiteError, match="offline mode"):
        sl.fetch_captions("https://youtu.be/x", tmp_path, "en", helper=helper, popen=popen)
    assert popen.made == []


def test_unpunctuated_captions_keep_their_lines():
    segments = [
        (float(i), i + 1.0, f"this is caption line number {i} without any stops") for i in range(10)
    ]
    unpunctuated = sl.Captions("t", "en", segments).text
    assert unpunctuated.count("\n") == 9
    punctuated = sl.Captions("t", "en", [(0.0, 1.0, "One sentence here. And another one.")]).text
    assert "\n" not in punctuated


# -- the quick look before choosing ----------------------------------------------


def info_line(**info):
    return _json.dumps({"title": "Talk", "duration": 1100.5, **info})


@pytest.mark.parametrize(
    ("info", "language", "found"),
    [
        ({"subtitles": {"en": []}}, "en", "written"),
        ({"subtitles": {"en-GB": []}}, "en", "written"),
        ({"automatic_captions": {"en-orig": [], "ar": []}}, "en", "automatic"),
        # "ar" there is a machine translation, not a real Arabic track.
        ({"automatic_captions": {"en-orig": [], "ar": []}}, "ar", None),
        ({"automatic_captions": {"de-orig": []}}, None, "automatic"),
        ({}, "en", None),
    ],
)
def test_captions_found_matches_what_fetch_takes(info, language, found):
    assert sl.captions_found(info, language) == found


def test_look_up_reads_title_length_and_captions(helper):
    lines = ["WARNING: no JS runtime", info_line(subtitles={"en": []})]
    found = sl.look_up(
        "https://youtu.be/x",
        "en",
        helper=helper,
        popen=lambda a: CaptionProcess(["x", "--output", str(helper)], {}, lines),
    )
    assert found == sl.VideoInfo("Talk", 1100.5, "written")


def test_look_up_failure_gets_a_plain_message(helper):
    lines = ["ERROR: [youtube] x: Private video"]
    with pytest.raises(sl.SiteError, match="private"):
        sl.look_up(
            "https://youtu.be/x",
            "en",
            helper=helper,
            popen=lambda a: CaptionProcess(["x", "--output", str(helper)], {}, lines),
        )


def test_look_up_without_a_length():
    found = sl.parse_info(_json.dumps({"title": "Live"}), "en")
    assert found.duration is None and found.captions is None
