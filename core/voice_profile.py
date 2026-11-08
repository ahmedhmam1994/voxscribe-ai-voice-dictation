"""Your voice profile: two answers set VoxScribe up for your work, so a nurse
gets drug names right on the first dictation without opening Settings.

- "What do you mostly write?" switches on the word pack, spoken formats and
  tools for that field.
- "Where do you write most?" picks the dictation mode (core/modes.py): full
  sentences for email, no final full stop in chats, and so on. With Pro,
  modes still switch by themselves with the focused app.

Asked once in the first-run welcome (app/welcome.py) and changeable on the My
words page. Choosing a field only switches things on; it never deletes your
own words, replacements or imported packs. Switching to another field swaps
the built-in pack of the old field for the new one.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSettings

from core import settings
from core.term_packs import BUILTIN_PACKS


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    hint: str
    pack: str | None = None
    spoken_formats: bool = False
    code: bool = False


FIELDS: tuple[Field, ...] = (
    Field("everyday", "Everyday writing", "Messages, email and notes."),
    Field(
        "medical",
        "Medicine or care",
        "Drug names and doses, written like a chart: 5 mg BID, 120/80.",
        pack="medical",
        spoken_formats=True,
    ),
    Field(
        "legal",
        "Law",
        "Legal terms and references: Section 12(b), Smith v. Jones.",
        pack="legal",
        spoken_formats=True,
    ),
    Field(
        "business",
        "Business",
        "Business terms and figures: $50,000, Q3, 20%.",
        pack="business",
        spoken_formats=True,
    ),
    Field(
        "code",
        "Software and code",
        "Say names and symbols, get code: camel case user name becomes userName (Pro).",
        code=True,
    ),
)


@dataclass(frozen=True)
class AppChoice:
    id: str
    label: str
    hint: str
    mode: str


APPS: tuple[AppChoice, ...] = (
    AppChoice(
        "mixed", "A bit of everything", "Your settings as they are, in every app.", "default"
    ),
    AppChoice("email", "Email", "Full sentences with punctuation, the way email reads.", "email"),
    AppChoice("chat", "Chat apps", "Short messages, no full stop at the end.", "chat"),
    AppChoice("docs", "Documents and notes", "Clean sentences, nothing rewritten.", "notes"),
    AppChoice("code", "A code editor", "Code dictation everywhere (Pro).", "code"),
)

DEFAULT_FIELD = "everyday"
DEFAULT_APP = "mixed"
_APPS_BY_ID = {choice.id: choice for choice in APPS}
_BY_ID = {field.id: field for field in FIELDS}
_FIELD_PACKS = {field.pack for field in FIELDS if field.pack}
assert _FIELD_PACKS <= {pack_id for pack_id, _ in BUILTIN_PACKS}


def _settings() -> QSettings:
    return QSettings("VoxScribe", "VoxScribe")


def field_by_id(field_id: str) -> Field:
    return _BY_ID.get(field_id, _BY_ID[DEFAULT_FIELD])


def get_field() -> str | None:
    """The field picked so far, or None before anyone answered."""
    value = _settings().value("voice_profile_field", "")
    return str(value) if value in _BY_ID else None


def packs_for(field_id: str, enabled: list[str]) -> list[str]:
    """`enabled` with the old field's built-in pack swapped for this field's.
    Imported packs and anything not tied to a field stay."""
    field = field_by_id(field_id)
    kept = [pack for pack in enabled if pack not in _FIELD_PACKS]
    return kept + [field.pack] if field.pack else kept


def apply_field(field_id: str) -> Field:
    """Saves the answer and switches on what the field needs."""
    field = field_by_id(field_id)
    _settings().setValue("voice_profile_field", field.id)
    settings.set_enabled_packs(packs_for(field.id, settings.get_enabled_packs()))
    if field.spoken_formats:
        settings.set_spoken_formats_enabled(True)
    if field.code:
        settings.set_code_dictation_enabled(True)
    return field


def app_by_id(app_id: str) -> AppChoice:
    return _APPS_BY_ID.get(app_id, _APPS_BY_ID[DEFAULT_APP])


def get_app() -> str | None:
    """Where you said you write most, or None before anyone answered."""
    value = _settings().value("voice_profile_app", "")
    return str(value) if value in _APPS_BY_ID else None


def apply_app(app_id: str) -> AppChoice:
    """Saves the answer and sets the dictation mode for it. A Pro mode (Code)
    simply does nothing until Pro is unlocked (core/modes.py)."""
    choice = app_by_id(app_id)
    _settings().setValue("voice_profile_app", choice.id)
    settings.set_mode(choice.mode)
    return choice
