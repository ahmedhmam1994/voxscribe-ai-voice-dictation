"""Fill-in templates -- a Pro feature (see core/license.py). A template is a
named block of text with `{slots}`. Say "template bug report" and VoxScribe
asks for each slot in turn; once the last one is answered, the finished text
is typed. Plain pattern matching, no model.

Different from a snippet (core/snippets.py), which pastes fixed text: a
template collects the variable parts by voice first.

Stored as JSON for the same reason snippets are: a body is free text that can
contain commas and line breaks.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime

from PySide6.QtCore import QSettings

_SLOT_RE = re.compile(r"\{([A-Za-z][A-Za-z0-9 _-]*)\}")

# Filled in automatically, never asked for.
_AUTO_SLOTS = {"date", "time"}

_TRIGGER_WORDS = ("template", "fill")
_CANCEL_WORDS = {"cancel", "cancel template", "stop"}
_SKIP_WORDS = {"skip", "next", "skip this"}


@dataclass(frozen=True)
class Template:
    name: str
    body: str


def _settings() -> QSettings:
    return QSettings("VoxScribe", "VoxScribe")


def get_templates() -> list[Template]:
    raw = _settings().value("templates", "")
    if not raw:
        return []
    try:
        items = json.loads(raw)
    except ValueError:
        return []
    return [
        Template(str(name), str(body))
        for name, body in items
        if isinstance(name, str) and isinstance(body, str)
    ]


def set_templates(templates: list[Template]) -> None:
    cleaned = [(t.name.strip(), t.body) for t in templates if t.name.strip() and t.body]
    _settings().setValue("templates", json.dumps(cleaned))


def _normalize(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text).strip().lower()


def slot_names(body: str) -> list[str]:
    """The slots to ask for, in order of first appearance, without repeats."""
    seen: list[str] = []
    for match in _SLOT_RE.finditer(body):
        name = match.group(1).strip()
        if name.lower() not in _AUTO_SLOTS and name not in seen:
            seen.append(name)
    return seen


def find_template(text: str, templates: list[Template]) -> Template | None:
    """The template named by a spoken "template <name>" or "fill <name>", if the
    whole utterance is exactly that."""
    spoken = _normalize(text)
    for template in templates:
        name = _normalize(template.name)
        if any(spoken == f"{word} {name}" for word in _TRIGGER_WORDS):
            return template
    return None


class TemplateSession:
    """One template being filled by voice, a slot at a time."""

    def __init__(self, template: Template, now: datetime | None = None) -> None:
        self._template = template
        self._slots = slot_names(template.body)
        self._values: dict[str, str] = {}
        self._now = now or datetime.now()

    @property
    def name(self) -> str:
        return self._template.name

    @property
    def prompt(self) -> str | None:
        """The slot being asked for, or None once every slot is answered."""
        answered = len(self._values)
        return self._slots[answered] if answered < len(self._slots) else None

    @property
    def finished(self) -> bool:
        return self.prompt is None

    def feed(self, spoken: str) -> str:
        """Takes one spoken answer. Returns "cancel", "skip" or "filled"."""
        said = _normalize(spoken)
        if said in _CANCEL_WORDS:
            return "cancel"
        if self.prompt is None:
            return "filled"
        if said in _SKIP_WORDS:
            self._values[self.prompt] = ""
            return "skip"
        self._values[self.prompt] = _tidy_answer(spoken)
        return "filled"

    def result(self) -> str:
        """The template text with every answered slot filled in."""

        def fill(match: re.Match[str]) -> str:
            name = match.group(1).strip()
            lowered = name.lower()
            if lowered == "date":
                return self._now.strftime("%Y-%m-%d")
            if lowered == "time":
                return self._now.strftime("%H:%M")
            return self._values.get(name, "")

        return _SLOT_RE.sub(fill, self._template.body)


def _tidy_answer(spoken: str) -> str:
    """Drops the full stop Whisper adds after a one-sentence answer."""
    answer = spoken.strip()
    if answer.endswith(".") and answer.count(".") == 1:
        answer = answer[:-1]
    return answer


def format_lines(items: list[Template]) -> str:
    """The settings text box form: one `name => body` line each, with line breaks
    in a body written as a backslash and n."""
    return "\n".join(f"{t.name} => {t.body.replace(chr(10), chr(92) + 'n')}" for t in items)


def parse_lines(text: str) -> list[Template]:
    """The reverse of format_lines. Lines without `=>`, a name or a body are skipped."""
    items = []
    for line in text.splitlines():
        name, arrow, body = line.partition("=>")
        if arrow and name.strip() and body.strip():
            items.append(Template(name.strip(), body.strip().replace(chr(92) + "n", "\n")))
    return items
