"""Import the audio of a video site link (YouTube and similar sites).

The audio is fetched by yt-dlp, a free open source download helper. It is not
bundled with the app: it is downloaded once, on first use, from its official
release page and checked against the checksum published with it, then kept in
the app data folder. Only the audio is downloaded, and it is transcribed on
this PC with the user's own model and word lists, like any imported file.
Nothing is sent to an online transcription service.

The helper runs as its own process, outside core/network_guard.py, so this
module checks offline mode itself before starting it and logs the site's host.

Pure and testable: the network and the helper process are reached only through
`opener` and `popen` arguments, so tests pass fakes.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import queue
import re
import shutil
import subprocess
import threading
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from core import batch, link_import, network_guard, srt

_APP_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "VoxScribe"
HELPER_DIR = _APP_DIR / "helpers"
HELPER_NAME = "yt-dlp.exe"
HELPER_PATH = HELPER_DIR / HELPER_NAME
RELEASE_BASE = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/"
SUMS_NAME = "SHA2-256SUMS"
HELPER_MAX_BYTES = 200 * 1024**2  # far above its real size (about 23 MB)
HELPER_SIZE_TEXT = "about 23 MB"

# Hosts that are always web pages, so the direct download is not even tried.
_SITE_HOSTS = (
    "youtube.com",
    "youtu.be",
    "youtube-nocookie.com",
    "vimeo.com",
    "soundcloud.com",
    "dailymotion.com",
    "twitch.tv",
    "tiktok.com",
    "x.com",
    "twitter.com",
    "facebook.com",
    "fb.watch",
    "instagram.com",
    "rumble.com",
    "bilibili.com",
    "ted.com",
    "archive.org",
)

_PROGRESS_PREFIX = "VXPROG"
_PATH_PREFIX = "VXPATH"


class SiteError(link_import.LinkError):
    """A failure worth showing as is. `can_update` is True when a newer helper
    might fix it (sites change, and the helper follows them)."""

    def __init__(self, message: str, *, can_update: bool = False) -> None:
        super().__init__(message)
        self.can_update = can_update


class HelperMissing(Exception):
    """The helper has not been downloaded yet; ask before fetching it."""


def is_site(url: str) -> bool:
    """True for links to a known video site (handled here, not as a file)."""
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in _SITE_HOSTS)


def host_of(url: str) -> str:
    return (urllib.parse.urlsplit(url).hostname or "").lower()


# -- the helper ----------------------------------------------------------------


def is_installed(path: Path | None = None) -> bool:
    path = path or HELPER_PATH
    try:
        return path.is_file() and path.stat().st_size > 1024 * 1024
    except OSError:
        return False


def expected_hash(sums_text: str, name: str = HELPER_NAME) -> str | None:
    """The SHA-256 for `name` in a SHA2-256SUMS file ("<hash>  <name>" lines)."""
    for line in sums_text.splitlines():
        parts = line.strip().split()
        if len(parts) == 2 and parts[1].lstrip("*") == name and re.fullmatch(
            r"[0-9a-fA-F]{64}", parts[0]
        ):
            return parts[0].lower()
    return None


def _open(url: str) -> object:
    request = urllib.request.Request(url, headers={"User-Agent": link_import.USER_AGENT})
    return urllib.request.urlopen(request, timeout=link_import.TIMEOUT_SECONDS)  # noqa: S310 -- fixed https URL


def install_helper(
    *,
    target: Path | None = None,
    opener: Callable[[str], object] = _open,
    progress: Callable[[int, int | None], None] | None = None,
    should_stop: Callable[[], bool] = lambda: False,
) -> Path:
    """Downloads the helper from its official release, checks it against the
    published checksum, and only then puts it in place. Also used to update it.
    Raises SiteError, link_import.Cancelled, or a network error."""
    target = target or HELPER_PATH
    response = opener(RELEASE_BASE + SUMS_NAME)
    try:
        sums = response.read(1024 * 1024).decode("utf-8", "replace")
    finally:
        getattr(response, "close", lambda: None)()
    wanted = expected_hash(sums)
    if not wanted:
        raise SiteError("Could not check the download helper (its checksum list was not found).")

    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    digest = hashlib.sha256()
    response = opener(RELEASE_BASE + HELPER_NAME)
    try:
        try:
            total = int(response.headers.get("Content-Length") or 0) or None
        except (AttributeError, ValueError):
            total = None
        done = 0
        with partial.open("wb") as handle:
            while True:
                if should_stop():
                    raise link_import.Cancelled()
                chunk = response.read(link_import.CHUNK)
                if not chunk:
                    break
                done += len(chunk)
                if done > HELPER_MAX_BYTES:
                    raise SiteError(
                        "The download helper was larger than expected, so it was not kept."
                    )
                digest.update(chunk)
                handle.write(chunk)
                if progress:
                    progress(done, total)
        if digest.hexdigest() != wanted:
            raise SiteError(
                "The download helper did not match its published checksum, so it was "
                "not kept. Try again later."
            )
        partial.replace(target)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    finally:
        getattr(response, "close", lambda: None)()
    return target


# -- running it ----------------------------------------------------------------


def build_args(
    helper: Path, url: str, folder: Path, max_bytes: int = link_import.MAX_BYTES
) -> list[str]:
    """The helper's command line: audio only, one video (never a whole
    playlist), no live streams, a size cap, our own progress lines."""
    return [
        str(helper),
        "--ignore-config",
        "--no-playlist",
        "--no-mtime",
        "--windows-filenames",
        "--encoding",
        "utf-8",
        "--format",
        "bestaudio/best",
        "--match-filter",
        "!is_live",
        "--max-filesize",
        str(max_bytes),
        "--output",
        str(folder / "%(title).80B [%(id)s].%(ext)s"),
        "--newline",
        "--progress",
        "--progress-template",
        f"download:{_PROGRESS_PREFIX} %(progress.downloaded_bytes)s "
        "%(progress.total_bytes)s %(progress.total_bytes_estimate)s",
        "--print",
        f"after_move:{_PATH_PREFIX} %(filepath)s",
        "--",
        url,
    ]


def parse_progress(line: str) -> tuple[int, int | None] | None:
    """(done bytes, total bytes or None) from one of our progress lines."""
    parts = line.strip().split()
    if len(parts) != 4 or parts[0] != _PROGRESS_PREFIX:
        return None

    def number(text: str) -> int | None:
        try:
            return int(float(text))
        except ValueError:
            return None  # "NA" while the size is unknown

    done = number(parts[1])
    if done is None:
        return None
    return done, number(parts[2]) or number(parts[3])


def parse_path(line: str) -> str | None:
    line = line.strip()
    if line.startswith(_PATH_PREFIX + " "):
        return line[len(_PATH_PREFIX) + 1 :].strip() or None
    return None


_OUTDATED_HINT = (
    "The site may have changed, and the download helper may need an update."
)

# (pattern, message, can_update); the first match wins.
_ERRORS: tuple[tuple[str, str, bool], ...] = (
    (r"offline mode", "", False),
    (r"private video", "That video is private, so it cannot be downloaded.", False),
    (
        r"not a bot",
        "The site asked for a sign-in to check you are not a bot. Try again later, or "
        "save the file another way and use Import Audio.",
        False,
    ),
    (
        r"confirm your age|age.restricted|inappropriate for some users",
        "That video is age restricted and needs a sign-in, so it cannot be downloaded.",
        False,
    ),
    (
        r"members.only|join this channel|premium",
        "That video is only for paying members, so it cannot be downloaded.",
        False,
    ),
    (
        r"available in your country|geo.?restrict|available in your region",
        "That video is not available in your country.",
        False,
    ),
    (
        r"is live|live event|does not pass filter|premiere",
        "Live streams and premieres cannot be imported. Try again after it has ended.",
        False,
    ),
    (
        r"larger than max-filesize",
        "That audio is larger than 2 GB, the most that can be imported from a link.",
        False,
    ),
    (
        r"unsupported url",
        "VoxScribe cannot read that site. Use a link that points straight at the file, "
        "or save it yourself and use Import Audio.",
        False,
    ),
    (
        r"video (?:is )?unavailable|has been removed|does not exist|"
        r"http error 404",
        "That video is not available. It may have been removed or made private.",
        False,
    ),
    (
        r"http error 429|too many requests",
        "That site is limiting downloads right now. Try again later.",
        False,
    ),
    (
        r"getaddrinfo|failed to resolve|unable to download webpage|timed out|"
        r"connection (?:refused|reset|aborted)|network is unreachable",
        "Could not reach that site. Check the link and your internet connection.",
        False,
    ),
    (
        r"unable to extract|signature|nsig|requested format is not available|"
        r"latest version|http error 403",
        _OUTDATED_HINT,
        True,
    ),
)


def friendly_site_error(output: str) -> SiteError:
    """A plain message from the helper's error output."""
    errors = [line for line in output.splitlines() if line.startswith("ERROR")]
    text = "\n".join(errors) or output
    lowered = text.lower()
    for pattern, message, can_update in _ERRORS:
        if re.search(pattern, lowered):
            if not message:  # our own offline message passes through
                return SiteError(text.strip())
            return SiteError(message, can_update=can_update)
    tail = output.strip().splitlines()
    detail = errors[0] if errors else (tail[-1] if tail else "no details")
    detail = re.sub(r"^ERROR:\s*", "", detail)[:200]
    return SiteError(f"The download failed: {detail}", can_update=True)


def _popen(args: list[str]) -> subprocess.Popen:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.Popen(  # noqa: S603 -- fixed helper path and our own arguments
        args,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=flags,
        env=env,
    )


def _stop(process: subprocess.Popen) -> None:
    """Ends the helper and its child (the helper is a self-unpacking program
    that runs a second process)."""
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(  # noqa: S603, S607 -- Windows tool, fixed arguments
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    try:
        process.kill()
    except OSError:
        pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass


_POLL_SECONDS = 0.25


def _lines(stream: Iterable[bytes], should_stop: Callable[[], bool]) -> Iterable[str]:
    """The helper's output lines, read on a side thread so a stop request is
    noticed even while the helper prints nothing."""
    lines: queue.Queue[str | None] = queue.Queue()

    def pump() -> None:
        try:
            for raw in stream:
                lines.put(raw.decode("utf-8", "replace").rstrip("\r\n"))
        finally:
            lines.put(None)

    threading.Thread(target=pump, daemon=True).start()
    while True:
        if should_stop():
            raise link_import.Cancelled()
        try:
            line = lines.get(timeout=_POLL_SECONDS)
        except queue.Empty:
            continue
        if line is None:
            return
        yield line


def _ready_helper(url: str, helper: Path | None) -> Path:
    """Checks the link, offline mode and the helper, then logs the host."""
    helper = helper or HELPER_PATH
    problem = link_import.check_url(url)
    if problem:
        raise SiteError(problem)
    if network_guard.is_blocking():
        raise SiteError(f"VoxScribe offline mode is on, so it cannot reach {host_of(url)}.")
    if not is_installed(helper):
        raise HelperMissing()
    network_guard.note(host_of(url))
    return helper


def _run(
    process: object,
    should_stop: Callable[[], bool],
    progress: Callable[[int, int | None], None] | None,
) -> tuple[str, str | None]:
    """Reads the helper until it ends: (the tail of its output, saved path)."""
    output: list[str] = []
    saved: str | None = None
    try:
        for line in _lines(process.stdout, should_stop):
            step = parse_progress(line)
            if step is not None:
                if progress:
                    progress(*step)
                continue
            found = parse_path(line)
            if found:
                saved = found
                continue
            output.append(line)
            del output[:-200]  # keep the tail only
        process.wait()
    except BaseException:
        _stop(process)
        raise
    if should_stop():
        raise link_import.Cancelled()
    return "\n".join(output), saved


def download_audio(
    url: str,
    folder: Path = link_import.DEFAULT_FOLDER,
    *,
    helper: Path | None = None,
    popen: Callable[[list[str]], object] = _popen,
    progress: Callable[[int, int | None], None] | None = None,
    should_stop: Callable[[], bool] = lambda: False,
    max_bytes: int = link_import.MAX_BYTES,
) -> Path:
    """Downloads the audio of a video site link into `folder` and returns it.

    It works in a fresh folder inside `folder` and moves only the finished
    file out, so a failed or stopped download leaves nothing behind.
    Raises HelperMissing, SiteError, or link_import.Cancelled."""
    helper = _ready_helper(url, helper)
    work = folder / f".incoming-{uuid.uuid4().hex[:8]}"
    work.mkdir(parents=True, exist_ok=True)
    try:
        process = popen(build_args(helper, url, work, max_bytes))
        text, saved = _run(process, should_stop, progress)
        result = Path(saved) if saved else None
        if result is None or not result.is_file():
            # Without a saved file the helper either failed or skipped the
            # video (too large, live), which it reports on a normal line.
            raise friendly_site_error(text or "The helper stopped without saving anything.")
        if not batch.is_media(result.name):
            raise SiteError("The site sent something that is not audio or video.")
        target = link_import.unused_path(folder, link_import.safe_name(result.name))
        shutil.move(str(result), str(target))
        return target
    finally:
        shutil.rmtree(work, ignore_errors=True)


# -- the site's own captions --------------------------------------------------


class NoCaptions(SiteError):
    """The video has no captions in the wanted language."""


@dataclass
class Captions:
    title: str
    language: str
    segments: list[tuple[float, float, str]]
    srt_path: Path | None = None

    @property
    def text(self) -> str:
        """Running text. Automatic captions usually have no punctuation; then
        each caption line stays on its own line, so a summary still finds
        sentence-sized pieces instead of one endless sentence."""
        joined = captions_text(self.segments)
        words = len(joined.split())
        ends = len(re.findall(r"[.!?؟。]", joined))
        if words > 40 and ends * 40 < words:
            return "\n".join(text for _, _, text in self.segments)
        return joined


_CUE_TIMING = re.compile(r"^\s*([\d:.,]+)\s+-->\s+([\d:.,]+)")
_TAG = re.compile(r"<[^>]*>")
_SOUND_ONLY = re.compile(r"^\[[^\]]*\]$")  # [Music], [Applause]


def _seconds(stamp: str) -> float:
    total = 0.0
    for part in stamp.replace(",", ".").split(":"):
        total = total * 60 + float(part)
    return total


def parse_vtt(text: str) -> list[tuple[float, float, str]]:
    """(start, end, text) cards from a WebVTT file.

    Automatic captions repeat the previous line at the top of each new card
    (the rolling style) and carry word timing tags; both are removed, so
    every spoken line appears once."""
    segments: list[tuple[float, float, str]] = []
    recent: list[str] = []
    for block in re.split(r"\r?\n\s*\r?\n", text.replace("﻿", "")):
        lines = block.splitlines()
        timing = None
        at = 0
        for at, line in enumerate(lines):
            timing = _CUE_TIMING.match(line)
            if timing:
                break
        if timing is None:
            continue
        try:
            start, end = _seconds(timing.group(1)), _seconds(timing.group(2))
        except ValueError:
            continue
        fresh = []
        for raw in lines[at + 1 :]:
            clean = html.unescape(_TAG.sub("", raw)).replace(" ", " ")
            clean = " ".join(clean.split())
            if not clean or clean in recent or _SOUND_ONLY.match(clean):
                continue
            fresh.append(clean)
            recent = (recent + [clean])[-3:]
        if fresh:
            segments.append((start, end, " ".join(fresh)))
    return segments


def captions_text(segments: list[tuple[float, float, str]]) -> str:
    return " ".join(" ".join(text for _, _, text in segments).split())


def caption_languages(language: str | None, automatic: bool = False) -> str:
    """The helper's --sub-langs value.

    Written captions: the dictation language and its regional forms (English
    when it is set to detect automatically). Automatic captions: only the
    original track ("-orig", the language actually spoken). A plain language
    code there would be a machine translation, which is never wanted, and the
    site also limits how often those can be fetched."""
    if automatic:
        return f"{language.lower()}-orig" if language else ".*-orig"
    lang = (language or "en").lower()
    return f"{lang},{lang}-.*"


def _best_vtt(files: list[Path], lang: str) -> Path | None:
    def rank(path: Path) -> tuple[int, str]:
        code = path.suffixes[-2].lstrip(".").lower() if len(path.suffixes) >= 2 else ""
        return ({lang: 0, f"{lang}-orig": 1}.get(code, 2), path.name)

    return min(files, key=rank) if files else None


def caption_args(
    helper: Path, url: str, folder: Path, language: str | None, automatic: bool = False
) -> list[str]:
    """Captions only: the small caption file, no audio or video."""
    return [
        str(helper),
        "--ignore-config",
        "--no-playlist",
        "--windows-filenames",
        "--encoding",
        "utf-8",
        "--skip-download",
        "--write-auto-subs" if automatic else "--write-subs",
        "--sub-langs",
        caption_languages(language, automatic),
        "--sub-format",
        "vtt",
        "--output",
        str(folder / "%(title).80B [%(id)s].%(ext)s"),
        "--",
        url,
    ]


_LANGUAGE_NAMES = {
    "en": "English", "ar": "Arabic", "fr": "French", "de": "German", "es": "Spanish",
    "it": "Italian", "pt": "Portuguese", "ru": "Russian", "tr": "Turkish", "hi": "Hindi",
    "ur": "Urdu", "zh": "Chinese", "ja": "Japanese", "ko": "Korean", "nl": "Dutch",
}  # fmt: skip


def language_name(code: str) -> str:
    return _LANGUAGE_NAMES.get(code, f"the language set in VoxScribe ({code})")


def fetch_captions(
    url: str,
    folder: Path = link_import.DEFAULT_FOLDER,
    language: str | None = None,
    *,
    save_srt: bool = False,
    helper: Path | None = None,
    popen: Callable[[list[str]], object] = _popen,
    should_stop: Callable[[], bool] = lambda: False,
) -> Captions:
    """The site's own captions for a video, as text (and an .srt file in
    `folder` when `save_srt`). Only the small caption file is downloaded.
    Raises NoCaptions, HelperMissing, SiteError or link_import.Cancelled."""
    helper = _ready_helper(url, helper)
    lang = (language or "en").lower()
    work = folder / f".incoming-{uuid.uuid4().hex[:8]}"
    work.mkdir(parents=True, exist_ok=True)
    try:
        best = None
        # Captions people wrote first, then the site's automatic ones.
        for automatic in (False, True):
            process = popen(caption_args(helper, url, work, language, automatic))
            text, _ = _run(process, should_stop, None)
            best = _best_vtt(sorted(work.glob("*.vtt")), lang)
            if best is not None:
                break
            if "ERROR" in text:
                raise friendly_site_error(text)
        if best is None:
            raise NoCaptions(
                f"That video has no captions in {language_name(lang)}."
                if language
                else "That video has no captions."
            )
        segments = parse_vtt(best.read_text(encoding="utf-8", errors="replace"))
        if not segments:
            raise NoCaptions("That video's captions are empty.")
        # "Title [id].en.vtt" -> "Title [id]"
        title = best.name[: -len("".join(best.suffixes[-2:]))] or "captions"
        result = Captions(title=title, language=lang, segments=segments)
        if save_srt:
            target = link_import.unused_path(
                folder, link_import.safe_name(f"{title} (site captions).srt")
            )
            target.write_text(srt.format_srt(segments), encoding="utf-8")
            result.srt_path = target
        return result
    finally:
        shutil.rmtree(work, ignore_errors=True)


@dataclass(frozen=True)
class VideoInfo:
    """What a quick look at a video link found, without downloading it."""

    title: str
    duration: float | None  # seconds, None when the site does not say
    captions: str | None  # "written", "automatic" or None


def info_args(helper: Path, url: str) -> list[str]:
    return [
        str(helper),
        "--ignore-config",
        "--no-playlist",
        "--encoding",
        "utf-8",
        "--skip-download",
        "--dump-json",
        "--",
        url,
    ]


def captions_found(info: dict, language: str | None) -> str | None:
    """'written' when someone wrote captions in the language, 'automatic' when
    only the site's own track in the spoken language exists, else None. The
    same choice fetch_captions makes, so the two always agree."""
    lang = (language or "en").lower()
    written = [k.lower() for k in (info.get("subtitles") or {})]
    if any(k == lang or k.startswith(lang + "-") for k in written):
        return "written"
    automatic = [k.lower() for k in (info.get("automatic_captions") or {})]
    wanted = f"{lang}-orig" if language else None
    if any(k == wanted if wanted else k.endswith("-orig") for k in automatic):
        return "automatic"
    return None


def parse_info(output: str, language: str | None) -> VideoInfo | None:
    """Reads the helper's JSON line; None when there is none."""
    for line in reversed(output.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            info = json.loads(line)
        except ValueError:
            continue
        try:
            duration = float(info.get("duration")) if info.get("duration") else None
        except (TypeError, ValueError):
            duration = None
        return VideoInfo(
            title=str(info.get("title") or "this video"),
            duration=duration,
            captions=captions_found(info, language),
        )
    return None


def look_up(
    url: str,
    language: str | None = None,
    *,
    helper: Path | None = None,
    popen: Callable[[list[str]], object] = _popen,
    should_stop: Callable[[], bool] = lambda: False,
) -> VideoInfo:
    """Title, length and available captions of a video link, in a few
    seconds, nothing downloaded. Raises HelperMissing, SiteError, Cancelled."""
    helper = _ready_helper(url, helper)
    process = popen(info_args(helper, url))
    text, _ = _run_keep_all(process, should_stop)
    found = parse_info(text, language)
    if found is None:
        raise friendly_site_error(text or "The helper gave no details about that link.")
    return found


def _run_keep_all(process: object, should_stop: Callable[[], bool]) -> tuple[str, None]:
    """Like _run, but keeps every line (the details arrive as one long line)."""
    lines: list[str] = []
    try:
        for line in _lines(process.stdout, should_stop):
            lines.append(line)
        process.wait()
    except BaseException:
        _stop(process)
        raise
    if should_stop():
        raise link_import.Cancelled()
    return "\n".join(lines), None


@dataclass(frozen=True)
class Plan:
    """How a link will be handled: as a file, or through the site helper."""

    site: bool
    needs_helper: bool


def plan_for(url: str, helper: Path | None = None) -> Plan:
    site = is_site(url)
    return Plan(site=site, needs_helper=site and not is_installed(helper))
