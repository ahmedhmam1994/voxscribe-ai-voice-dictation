"""Persisted user settings (QSettings-backed, Windows registry under the
hood): the global hold-to-talk hotkey and its talk mode (hold vs. toggle),
whether VoxScribe launches automatically at Windows sign-in, the preferred
microphone device, the dictation language, whether filler-word cleanup
runs, a custom vocabulary list, an app-exclusion list, the Whisper model
size, whether recording plays a sound, and local usage stats.

The available hotkey choices are curated to F-keys and a few rarely-typed
keys rather than allowing an arbitrary key: since this is a *global*
hold-to-talk hotkey (registered system-wide, not just while VoxScribe has
focus), letting it land on a normal typing key (a letter, digit, space,
etc.) would make that key stop working for typing anywhere on the system
while VoxScribe is running.
"""

from __future__ import annotations

import sys
import winreg
from pathlib import Path

from PySide6.QtCore import QSettings

DEFAULT_HOTKEY = "f9"

AVAILABLE_HOTKEYS = [
    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
    "pause", "scroll lock", "insert",
]

_AUTO_START_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
_AUTO_START_VALUE_NAME = "VoxScribe"


def _settings() -> QSettings:
    return QSettings("VoxScribe", "VoxScribe")


def get_hotkey() -> str:
    value = _settings().value("hotkey", DEFAULT_HOTKEY)
    return value if value in AVAILABLE_HOTKEYS else DEFAULT_HOTKEY


def set_hotkey(key: str) -> None:
    _settings().setValue("hotkey", key)


def _launch_command() -> str:
    """The command Windows should run at sign-in to relaunch VoxScribe.

    A frozen PyInstaller build's sys.executable *is* VoxScribe.exe, so it's
    launched directly. Running from source (python main.py during
    development), sys.executable is the interpreter, not the app -- point it
    at this repo's own main.py explicitly, or Windows would launch a bare
    Python REPL at sign-in instead of the app.
    """
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    main_py = Path(__file__).resolve().parent.parent / "main.py"
    return f'"{sys.executable}" "{main_py}"'


def get_auto_start() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _AUTO_START_KEY_PATH) as key:
            winreg.QueryValueEx(key, _AUTO_START_VALUE_NAME)
            return True
    except FileNotFoundError:
        return False


def set_auto_start(enabled: bool) -> None:
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, _AUTO_START_KEY_PATH, 0, winreg.KEY_SET_VALUE
    ) as key:
        if enabled:
            winreg.SetValueEx(
                key, _AUTO_START_VALUE_NAME, 0, winreg.REG_SZ, _launch_command()
            )
        else:
            try:
                winreg.DeleteValue(key, _AUTO_START_VALUE_NAME)
            except FileNotFoundError:
                pass


def get_input_device() -> int | None:
    """None means auto-detect (the previous, only behavior) -- QSettings'
    Windows registry backend round-trips values as strings, so an empty
    string is the stored form of "no preference" rather than a missing key."""
    value = _settings().value("input_device", "")
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def set_input_device(device: int | None) -> None:
    _settings().setValue("input_device", "" if device is None else device)


DEFAULT_LANGUAGE = "en"

# (ISO 639-1 code or None for auto-detect, display name). DEFAULT_MODEL_SIZE
# in core/transcribe.py ("small", not "small.en") is already the
# multilingual Whisper model -- these aren't a different/bigger download,
# just previously-unexposed capability of the model already on disk. Not
# exhaustive (Whisper supports ~100 languages total) -- a practical, common
# subset rather than every possible code.
AVAILABLE_LANGUAGES: list[tuple[str | None, str]] = [
    (None, "Auto-detect"),
    ("en", "English"),
    ("es", "Spanish"),
    ("fr", "French"),
    ("de", "German"),
    ("it", "Italian"),
    ("pt", "Portuguese"),
    ("nl", "Dutch"),
    ("ru", "Russian"),
    ("zh", "Chinese"),
    ("ja", "Japanese"),
    ("ko", "Korean"),
    ("ar", "Arabic"),
    ("hi", "Hindi"),
    ("tr", "Turkish"),
    ("pl", "Polish"),
    ("uk", "Ukrainian"),
    ("vi", "Vietnamese"),
    ("th", "Thai"),
    ("id", "Indonesian"),
    ("el", "Greek"),
    ("he", "Hebrew"),
    ("cs", "Czech"),
    ("ro", "Romanian"),
    ("hu", "Hungarian"),
    ("fi", "Finnish"),
    ("sv", "Swedish"),
    ("da", "Danish"),
    ("no", "Norwegian"),
]

_AVAILABLE_LANGUAGE_CODES = {code for code, _ in AVAILABLE_LANGUAGES}


def get_language() -> str | None:
    """None means auto-detect. Defaults to "en" (not auto-detect) so
    upgrading VoxScribe doesn't silently change transcription behavior for
    anyone who never opens Settings -- this preserves the hardcoded
    language="en" this app always used before this setting existed."""
    value = _settings().value("language", DEFAULT_LANGUAGE)
    if value in (None, ""):
        return None
    return value if value in _AVAILABLE_LANGUAGE_CODES else DEFAULT_LANGUAGE


def set_language(language: str | None) -> None:
    _settings().setValue("language", "" if language is None else language)


def get_cleanup_enabled() -> bool:
    """Default True, preserving this app's original always-on behavior --
    core/cleanup.py's filler-word/formatting pass ran unconditionally
    before this setting existed."""
    value = _settings().value("cleanup_enabled", True)
    # QSettings' Windows registry backend round-trips bools as the strings
    # "true"/"false", not Python bools -- normalize both forms.
    if isinstance(value, str):
        return value.lower() == "true"
    return bool(value)


def set_cleanup_enabled(enabled: bool) -> None:
    _settings().setValue("cleanup_enabled", enabled)


def get_custom_vocabulary() -> list[str]:
    """Names/acronyms/terms Whisper tends to mishear -- fed to faster-whisper
    as an `initial_prompt` hint (see core/transcribe.py) to bias recognition
    toward them, the closest local equivalent to Wispr Flow's Dictionary
    feature. Stored as one comma-separated string since QSettings' registry
    backend doesn't cleanly round-trip lists."""
    value = _settings().value("custom_vocabulary", "")
    if not value:
        return []
    return [term.strip() for term in value.split(",") if term.strip()]


def set_custom_vocabulary(terms: list[str]) -> None:
    _settings().setValue("custom_vocabulary", ", ".join(t.strip() for t in terms if t.strip()))


def custom_vocabulary_prompt() -> str | None:
    """The actual string to pass as faster-whisper's initial_prompt, or None
    if there's no custom vocabulary set. faster-whisper/Whisper treats this
    as prior context text -- listing the terms in a plain sentence-like
    form biases the decoder toward recognizing them without instructing the
    model to literally transcribe this text itself."""
    terms = get_custom_vocabulary()
    if not terms:
        return None
    return "Vocabulary that may come up: " + ", ".join(terms) + "."


DEFAULT_TALK_MODE = "hold"

AVAILABLE_TALK_MODES = [
    ("hold", "Hold to talk (release to stop)"),
    ("toggle", "Press to toggle (press again to stop)"),
]


def get_talk_mode() -> str:
    """"hold" preserves this app's original, only-ever behavior."""
    value = _settings().value("talk_mode", DEFAULT_TALK_MODE)
    valid = {mode for mode, _ in AVAILABLE_TALK_MODES}
    return value if value in valid else DEFAULT_TALK_MODE


def set_talk_mode(mode: str) -> None:
    _settings().setValue("talk_mode", mode)


def get_excluded_apps() -> list[str]:
    """Executable filenames (e.g. "keepass.exe") VoxScribe should refuse to
    dictate into, even via the global hotkey -- checked against
    core/focused_window.py's foreground_process_name() right before a
    recording starts."""
    value = _settings().value("excluded_apps", "")
    if not value:
        return []
    return [app.strip().lower() for app in value.split(",") if app.strip()]


def set_excluded_apps(apps: list[str]) -> None:
    _settings().setValue(
        "excluded_apps", ", ".join(a.strip().lower() for a in apps if a.strip())
    )


# Mirrors core/transcribe.py's DEFAULT_MODEL_SIZE ("small") as an independent
# literal rather than importing it -- core.transcribe imports faster_whisper,
# a heavy import not worth forcing on every caller of this settings module
# (e.g. tests/test_settings.py) just to read one string constant.
DEFAULT_MODEL_SIZE = "small"

AVAILABLE_MODEL_SIZES = [
    ("tiny", "Tiny -- fastest, least accurate (~75MB)"),
    ("base", "Base -- fast (~145MB)"),
    ("small", "Small -- recommended (~500MB)"),
    ("medium", "Medium -- more accurate (~1.5GB) (Pro)"),
    ("large", "Large -- most accurate (~3GB) (Pro)"),
]

# Larger models are gated behind a Pro license (see core/license.py) --
# free tier stays on tiny/base/small. Enforced both in the Settings UI
# (main_window.py disables these combo entries when not Pro) and as a
# defense-in-depth fallback in ModelLoaderThread, in case a size got
# persisted while Pro was active and the license was later removed.
PRO_MODEL_SIZES = {"medium", "large"}

_AVAILABLE_MODEL_SIZE_CODES = {code for code, _ in AVAILABLE_MODEL_SIZES}


def get_model_size() -> str:
    value = _settings().value("model_size", DEFAULT_MODEL_SIZE)
    return value if value in _AVAILABLE_MODEL_SIZE_CODES else DEFAULT_MODEL_SIZE


def set_model_size(size: str) -> None:
    _settings().setValue("model_size", size)


def get_sound_enabled() -> bool:
    """Default False: recording was always silent before this setting
    existed -- an upgrade shouldn't suddenly start beeping at anyone."""
    value = _settings().value("sound_enabled", False)
    if isinstance(value, str):
        return value.lower() == "true"
    return bool(value)


def set_sound_enabled(enabled: bool) -> None:
    _settings().setValue("sound_enabled", enabled)


def get_stats() -> tuple[int, int]:
    """(sessions, words) -- both 0 if VoxScribe has never transcribed
    anything since this setting was introduced. Purely local counters, never
    transmitted anywhere -- see docs/privacy.html's "no analytics" claim,
    which this doesn't change."""
    s = _settings()
    try:
        sessions = int(s.value("stats_sessions", 0))
    except (TypeError, ValueError):
        sessions = 0
    try:
        words = int(s.value("stats_words", 0))
    except (TypeError, ValueError):
        words = 0
    return sessions, words


def record_dictation(word_count: int) -> None:
    """Called once per successful (non-empty) transcription."""
    sessions, words = get_stats()
    s = _settings()
    s.setValue("stats_sessions", sessions + 1)
    s.setValue("stats_words", words + word_count)
