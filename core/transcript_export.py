"""More ways to save a transcribed file -- a Pro feature (see core/license.py).
Takes the same (start, end, text) segments core/srt.py does and writes
WebVTT captions, a timestamped Markdown transcript, or a Word document.

Pure formatting, no model: the Word file is built straight from its XML with
the standard library, so there is no extra dependency to ship.
"""

from __future__ import annotations

import io
import zipfile
from xml.sax.saxutils import escape

Segment = tuple[float, float, str]


def _clock(seconds: float, *, millis: bool = False, separator: str = ".") -> str:
    total_ms = round(seconds * 1000)
    hours, total_ms = divmod(total_ms, 3_600_000)
    minutes, total_ms = divmod(total_ms, 60_000)
    secs, ms = divmod(total_ms, 1_000)
    stamp = f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{stamp}{separator}{ms:03d}" if millis else stamp


def _spoken(segments: list[Segment]) -> list[Segment]:
    return [(start, end, text.strip()) for start, end, text in segments if text.strip()]


def format_vtt(segments: list[Segment]) -> str:
    """WebVTT captions: a WEBVTT header, then one cue per segment."""
    cues = [
        f"{_clock(start, millis=True)} --> {_clock(end, millis=True)}\n{text}\n"
        for start, end, text in _spoken(segments)
    ]
    return "WEBVTT\n\n" + "\n".join(cues)


def format_markdown(segments: list[Segment], title: str) -> str:
    """A heading, then one `[hh:mm:ss] text` line per segment."""
    lines = [f"# {title}"]
    lines += [f"**[{_clock(start)}]** {text}" for start, _end, text in _spoken(segments)]
    return "\n\n".join(lines) + "\n"


_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" '
    'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    "</Types>"
)
_ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    'Target="word/document.xml"/></Relationships>'
)


def _paragraph(text: str, *, bold: bool = False, size: int | None = None) -> str:
    props = ""
    if bold or size:
        props = "<w:rPr>" + ("<w:b/>" if bold else "") + (
            f'<w:sz w:val="{size}"/>' if size else ""
        ) + "</w:rPr>"
    return f'<w:p><w:r>{props}<w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'


def format_docx(segments: list[Segment], title: str) -> bytes:
    """A Word document: the title, then one `[hh:mm:ss] text` paragraph per segment."""
    body = _paragraph(title, bold=True, size=36)
    body += "".join(
        _paragraph(f"[{_clock(start)}] {text}") for start, _end, text in _spoken(segments)
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES)
        archive.writestr("_rels/.rels", _ROOT_RELS)
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()
