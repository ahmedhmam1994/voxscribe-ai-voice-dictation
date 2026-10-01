"""Formats transcribed segments as an SRT caption file.

Pure string formatting, no faster-whisper dependency, so it's cheap to
unit test on its own (see core/transcribe.py's `transcribe_file_segments`
for where the (start, end, text) tuples this expects come from).
"""

from __future__ import annotations


def _format_timestamp(seconds: float) -> str:
    """Seconds -> SRT's "HH:MM:SS,mmm" timestamp format."""
    total_ms = round(seconds * 1000)
    hours, total_ms = divmod(total_ms, 3_600_000)
    minutes, total_ms = divmod(total_ms, 60_000)
    secs, millis = divmod(total_ms, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_srt(segments: list[tuple[float, float, str]]) -> str:
    """Render (start, end, text) segments as SRT-formatted text.

    Segments with no text (e.g. a VAD-trimmed silent stretch) are skipped
    since an empty caption card is just noise in the output file.
    """
    blocks = []
    index = 1
    for start, end, text in segments:
        if not text.strip():
            continue
        blocks.append(
            f"{index}\n{_format_timestamp(start)} --> {_format_timestamp(end)}\n{text.strip()}\n"
        )
        index += 1
    return "\n".join(blocks)
