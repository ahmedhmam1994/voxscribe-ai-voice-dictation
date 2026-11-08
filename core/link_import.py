"""Download an audio or video file from a direct link, so it can be transcribed
like any imported file.

Pure and testable: no Qt, and the network is reached only through an `opener`
argument, so tests pass a fake one. Only the download needs the internet; the
transcription afterwards runs on this PC like every other import.

Only direct file links are handled here (a link that ends in a media file, or a
server that answers with audio or video). A link that opens a web page, such as
a video site, is refused with a plain message.
"""

from __future__ import annotations

import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from email.message import Message
from pathlib import Path

from core import batch

MAX_BYTES = 2 * 1024**3  # 2 GB
CHUNK = 256 * 1024
TIMEOUT_SECONDS = 30
USER_AGENT = "VoxScribe link import"
DEFAULT_FOLDER = Path.home() / "Documents" / "VoxScribe Links"

# Content types that are fine even without a media extension in the link.
_TYPE_TO_EXTENSION = {
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/aac": ".aac",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/wave": ".wav",
    "audio/flac": ".flac",
    "audio/x-flac": ".flac",
    "audio/ogg": ".ogg",
    "audio/webm": ".webm",
    "audio/opus": ".opus",
    "audio/x-ms-wma": ".wma",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
    "video/ogg": ".ogg",
}
_GENERIC_TYPES = {"application/octet-stream", "binary/octet-stream", "application/download", ""}


class LinkError(Exception):
    """A problem worth showing to the user as is."""


class WebPageLink(LinkError):
    """The link opens a web page. It may be a video site the site helper
    (core/site_link.py) can read."""


class Cancelled(Exception):
    """The user stopped the download."""


def clean_url(text: str) -> str:
    """The link from what was pasted: trimmed, surrounding quotes and angle
    brackets removed."""
    return text.strip().strip("<>\"'").strip()


def check_url(url: str) -> str | None:
    """None when the link can be tried, otherwise a message saying why not."""
    if not url:
        return "Paste a link first."
    if any(ch.isspace() for ch in url):
        return "That does not look like a single link."
    parts = urllib.parse.urlsplit(url)
    if parts.scheme.lower() not in ("http", "https"):
        return "Only web links that start with http:// or https:// can be imported."
    if not parts.hostname:
        return "That link has no website in it."
    return None


def _content_type(headers: Message) -> str:
    return (headers.get_content_type() if headers.get("Content-Type") else "").lower()


def _disposition_name(headers: Message) -> str | None:
    """The file name a server suggests in Content-Disposition, if any."""
    if not headers.get("Content-Disposition"):
        return None
    name = headers.get_filename()
    return name or None


def safe_name(name: str) -> str:
    """A file name Windows accepts: no folders, no reserved characters, not
    too long, never empty."""
    name = urllib.parse.unquote(name).replace("\\", "/").split("/")[-1]
    name = re.sub(r'[<>:"|?*\x00-\x1f]', "_", name).strip(" .")
    stem, ext = os.path.splitext(name)
    stem = stem[:80].strip(" .")
    if not stem or stem.upper() in {"CON", "PRN", "AUX", "NUL"} or re.fullmatch(
        r"(COM|LPT)\d", stem.upper()
    ):
        stem = "download"
    return stem + ext.lower()


def pick_name(url: str, headers: Message) -> str:
    """The file name to save as, with a media extension.

    Raises LinkError when the answer is clearly not audio or video, for example
    a web page."""
    ctype = _content_type(headers)
    suggested = _disposition_name(headers)
    from_url = urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1]
    candidates = [n for n in (suggested, from_url) if n]

    for candidate in candidates:
        name = safe_name(candidate)
        if batch.is_media(name):
            if ctype.startswith("text/"):
                break  # a page or an error message dressed up as a media link
            return name

    if ctype in _TYPE_TO_EXTENSION:
        stem = os.path.splitext(safe_name(candidates[0]))[0] if candidates else "download"
        return (stem or "download") + _TYPE_TO_EXTENSION[ctype]

    if ctype.startswith("text/html") or ctype.startswith("application/xhtml"):
        raise WebPageLink(
            "That link opens a web page, not an audio or video file. Use a link that "
            "points straight at the file (it usually ends in .mp3, .mp4, .m4a or .wav)."
        )
    if ctype.startswith(("audio/", "video/")):
        stem = os.path.splitext(safe_name(candidates[0]))[0] if candidates else "download"
        return (stem or "download") + (".mp4" if ctype.startswith("video/") else ".mp3")
    if ctype in _GENERIC_TYPES and candidates:
        raise LinkError(
            "That link does not look like an audio or video file. Use a link that ends "
            "in .mp3, .mp4, .m4a, .wav or another media type."
        )
    raise LinkError(f"That link points to a {ctype or 'file'} file, not audio or video.")


def unused_path(folder: Path, name: str) -> Path:
    """`folder/name`, or "name (2).ext" and so on, so nothing is overwritten."""
    target = folder / name
    stem, ext = os.path.splitext(name)
    n = 1
    while target.exists() or target.with_suffix(target.suffix + ".part").exists():
        n += 1
        target = folder / f"{stem} ({n}){ext}"
    return target


def _open(url: str) -> object:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS)  # noqa: S310 -- http(s) only, checked


def friendly_error(exc: BaseException) -> str:
    """A plain message for a failed download."""
    if isinstance(exc, LinkError):
        return str(exc)
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code in (401, 403):
            return "That site would not let the file be downloaded (it may need a sign-in)."
        if exc.code == 404:
            return "Nothing was found at that link (error 404). Check that it is complete."
        if exc.code == 429:
            return "That site is limiting downloads right now. Try again later."
        return f"The site answered with error {exc.code}."
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, OSError) and "offline mode" in str(reason):
            return str(reason)
        return "Could not reach that site. Check the link and your internet connection."
    if isinstance(exc, TimeoutError):
        return "The site took too long to answer. Try again later."
    if isinstance(exc, OSError) and "offline mode" in str(exc):
        return str(exc)
    if isinstance(exc, OSError):
        return f"Could not save the file: {exc.strerror or exc}"
    return f"The download failed: {exc}"


def download(
    url: str,
    folder: Path = DEFAULT_FOLDER,
    *,
    opener: Callable[[str], object] = _open,
    progress: Callable[[int, int | None], None] | None = None,
    should_stop: Callable[[], bool] = lambda: False,
    max_bytes: int = MAX_BYTES,
) -> Path:
    """Downloads `url` into `folder` and returns the saved file.

    `progress(done_bytes, total_bytes_or_None)` is called as data arrives.
    The file is written as "name.part" and renamed only when complete, so a
    failed or cancelled download never leaves a half file that looks finished.
    Raises LinkError (show the message), Cancelled, or a network error (pass
    it to friendly_error)."""
    problem = check_url(url)
    if problem:
        raise LinkError(problem)

    response = opener(url)
    try:
        final_url = getattr(response, "geturl", lambda: url)() or url
        if check_url(final_url):
            raise LinkError("That link redirected somewhere that cannot be downloaded.")
        headers = response.headers
        name = pick_name(final_url, headers)
        try:
            total = int(headers.get("Content-Length") or 0) or None
        except ValueError:
            total = None
        if total is not None and total > max_bytes:
            raise LinkError(
                f"That file is {total / 1024**3:.1f} GB. Files up to "
                f"{max_bytes / 1024**3:.0f} GB can be imported from a link."
            )

        folder.mkdir(parents=True, exist_ok=True)
        target = unused_path(folder, name)
        partial = target.with_suffix(target.suffix + ".part")
        done = 0
        try:
            with partial.open("wb") as handle:
                while True:
                    if should_stop():
                        raise Cancelled()
                    chunk = response.read(CHUNK)
                    if not chunk:
                        break
                    done += len(chunk)
                    if done > max_bytes:
                        raise LinkError(
                            f"That file is larger than {max_bytes / 1024**3:.0f} GB, "
                            "the most that can be imported from a link."
                        )
                    handle.write(chunk)
                    if progress:
                        progress(done, total)
            if done == 0:
                raise LinkError("That link gave back an empty file.")
            if total is not None and done < total:
                raise LinkError("The download stopped before the whole file arrived. Try again.")
            partial.replace(target)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise
        return target
    finally:
        close = getattr(response, "close", None)
        if close:
            close()


def percent(done: int, total: int | None) -> int | None:
    """Whole percent, or None when the size is unknown."""
    if not total:
        return None
    return max(0, min(100, int(done * 100 / total)))


def describe_size(done: int) -> str:
    """'12.3 MB' style text for progress when the total is unknown."""
    if done >= 1024**3:
        return f"{done / 1024**3:.2f} GB"
    return f"{done / 1024**2:.1f} MB"
