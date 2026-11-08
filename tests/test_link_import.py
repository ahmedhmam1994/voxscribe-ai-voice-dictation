"""Tests for core/link_import.py. No real network: a fake opener stands in."""

import io
import urllib.error
from email.message import Message

import pytest

from core import link_import as li


def headers(**values: str) -> Message:
    msg = Message()
    for key, value in values.items():
        msg[key.replace("_", "-")] = value
    return msg


class FakeResponse:
    def __init__(self, body: bytes, url: str, **head: str) -> None:
        self._body = io.BytesIO(body)
        self._url = url
        self.headers = headers(**head)
        self.closed = False

    def read(self, n: int) -> bytes:
        return self._body.read(n)

    def geturl(self) -> str:
        return self._url

    def close(self) -> None:
        self.closed = True


def opener_for(response: FakeResponse):
    calls = []

    def opener(url: str) -> FakeResponse:
        calls.append(url)
        return response

    opener.calls = calls
    return opener


# -- link checks ------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    ["https://example.com/a.mp3", "http://example.com/x", "HTTPS://Example.com/talk.mp4?x=1"],
)
def test_web_links_are_accepted(url):
    assert li.check_url(url) is None


@pytest.mark.parametrize(
    "url",
    ["", "file:///C:/secret.wav", "ftp://example.com/a.mp3", "example.com/a.mp3",
     "https:///nohost.mp3", "https://example.com/a b.mp3", "javascript:alert(1)"],
)  # fmt: skip
def test_other_links_are_refused(url):
    assert li.check_url(url)


def test_pasted_text_is_cleaned():
    assert li.clean_url('  "<https://example.com/a.mp3>"\n') == "https://example.com/a.mp3"


# -- file names -------------------------------------------------------------


def test_name_from_the_link():
    assert li.pick_name("https://x.org/pod/Episode%2012.MP3", headers()) == "Episode 12.mp3"


def test_server_suggested_name_wins():
    h = headers(Content_Type="audio/mpeg", Content_Disposition='attachment; filename="talk.mp3"')
    assert li.pick_name("https://x.org/download?id=7", h) == "talk.mp3"


def test_media_type_gives_the_extension_when_the_link_has_none():
    assert li.pick_name("https://x.org/stream/abc", headers(Content_Type="video/mp4")) == "abc.mp4"


def test_unknown_audio_type_still_gets_a_media_extension():
    name = li.pick_name("https://x.org/get", headers(Content_Type="audio/x-something"))
    assert name == "get.mp3"


def test_a_web_page_is_refused_with_a_plain_message():
    with pytest.raises(li.LinkError, match="web page"):
        li.pick_name("https://video.example/watch?v=1", headers(Content_Type="text/html"))


def test_a_page_pretending_to_be_media_is_refused():
    with pytest.raises(li.LinkError):
        li.pick_name("https://x.org/a.mp3", headers(Content_Type="text/html; charset=utf-8"))


def test_a_non_media_file_is_refused():
    with pytest.raises(li.LinkError):
        li.pick_name("https://x.org/report.pdf", headers(Content_Type="application/pdf"))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("../../evil.mp3", "evil.mp3"), ("a<b>:c?.wav", "a_b__c_.wav"), ("CON.mp3", "download.mp3"),
     ("...", "download"), ("x" * 200 + ".mp3", "x" * 80 + ".mp3")],
)  # fmt: skip
def test_safe_names(raw, expected):
    assert li.safe_name(raw) == expected


def test_unused_path_never_overwrites(tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"x")
    (tmp_path / "a (2).mp3.part").write_bytes(b"x")
    assert li.unused_path(tmp_path, "a.mp3").name == "a (3).mp3"


# -- download ---------------------------------------------------------------


def test_download_saves_the_whole_file_and_reports_progress(tmp_path):
    body = b"\x00" * (li.CHUNK * 2 + 10)
    resp = FakeResponse(body, "https://x.org/a.mp3", Content_Type="audio/mpeg",
                        Content_Length=str(len(body)))  # fmt: skip
    seen = []
    path = li.download("https://x.org/a.mp3", tmp_path, opener=opener_for(resp),
                       progress=lambda d, t: seen.append((d, t)))  # fmt: skip
    assert path == tmp_path / "a.mp3"
    assert path.read_bytes() == body
    assert seen[-1] == (len(body), len(body))
    assert resp.closed
    assert not list(tmp_path.glob("*.part"))


def test_the_folder_is_created(tmp_path):
    resp = FakeResponse(b"abc", "https://x.org/a.wav", Content_Type="audio/wav")
    path = li.download("https://x.org/a.wav", tmp_path / "new" / "dir", opener=opener_for(resp))
    assert path.exists()


def test_a_redirect_uses_the_final_name(tmp_path):
    resp = FakeResponse(b"abc", "https://cdn.x.org/real-name.m4a", Content_Type="audio/mp4")
    path = li.download("https://x.org/short", tmp_path, opener=opener_for(resp))
    assert path.name == "real-name.m4a"


def test_a_redirect_to_another_scheme_is_refused(tmp_path):
    resp = FakeResponse(b"abc", "file:///C:/x.mp3", Content_Type="audio/mpeg")
    with pytest.raises(li.LinkError):
        li.download("https://x.org/a.mp3", tmp_path, opener=opener_for(resp))


def test_too_big_by_header_is_refused_before_writing(tmp_path):
    resp = FakeResponse(b"abc", "https://x.org/a.mp3", Content_Type="audio/mpeg",
                        Content_Length="5000")  # fmt: skip
    with pytest.raises(li.LinkError, match="GB"):
        li.download("https://x.org/a.mp3", tmp_path, opener=opener_for(resp), max_bytes=1000)
    assert not any(tmp_path.iterdir())


def test_too_big_while_streaming_leaves_nothing(tmp_path):
    resp = FakeResponse(b"\x01" * 5000, "https://x.org/a.mp3", Content_Type="audio/mpeg")
    with pytest.raises(li.LinkError):
        li.download("https://x.org/a.mp3", tmp_path, opener=opener_for(resp), max_bytes=1000)
    assert not any(tmp_path.iterdir())


def test_cancel_leaves_nothing(tmp_path):
    resp = FakeResponse(b"\x01" * 5000, "https://x.org/a.mp3", Content_Type="audio/mpeg")
    with pytest.raises(li.Cancelled):
        li.download("https://x.org/a.mp3", tmp_path, opener=opener_for(resp),
                    should_stop=lambda: True)  # fmt: skip
    assert not any(tmp_path.iterdir())
    assert resp.closed


def test_a_short_download_is_an_error(tmp_path):
    resp = FakeResponse(b"abc", "https://x.org/a.mp3", Content_Type="audio/mpeg",
                        Content_Length="10")  # fmt: skip
    with pytest.raises(li.LinkError, match="before the whole file"):
        li.download("https://x.org/a.mp3", tmp_path, opener=opener_for(resp))
    assert not any(tmp_path.iterdir())


def test_an_empty_file_is_an_error(tmp_path):
    resp = FakeResponse(b"", "https://x.org/a.mp3", Content_Type="audio/mpeg")
    with pytest.raises(li.LinkError, match="empty"):
        li.download("https://x.org/a.mp3", tmp_path, opener=opener_for(resp))


def test_a_bad_link_never_reaches_the_network(tmp_path):
    def opener(url):  # noqa: ARG001
        raise AssertionError("must not be called")

    with pytest.raises(li.LinkError):
        li.download("file:///C:/x.mp3", tmp_path, opener=opener)


# -- messages ---------------------------------------------------------------


def _http(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://x.org", code, "x", Message(), None)


def test_friendly_errors():
    assert "404" in li.friendly_error(_http(404))
    assert "sign-in" in li.friendly_error(_http(403))
    assert "error 500" in li.friendly_error(_http(500))
    assert "reach" in li.friendly_error(urllib.error.URLError("dns"))
    offline = OSError("VoxScribe offline mode is on, so it cannot reach x.org.")
    assert "offline mode" in li.friendly_error(urllib.error.URLError(offline))
    assert "offline mode" in li.friendly_error(offline)
    assert li.friendly_error(li.LinkError("plain")) == "plain"


def test_messages_have_no_long_dashes():
    import inspect

    source = inspect.getsource(li)
    assert "\u2014" not in source and "\u2013" not in source


def test_progress_helpers():
    assert li.percent(50, 200) == 25
    assert li.percent(5, None) is None
    assert li.describe_size(5 * 1024**2) == "5.0 MB"
