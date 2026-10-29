"""Read it back: Windows' own text-to-speech reads a dictation aloud, so you can
catch a wrong word without looking at the screen. Uses the voices already on
this PC (System.Speech), offline, with nothing to download. If Windows has no
voice for the language of the text, nothing is heard.

The text goes to PowerShell through an environment variable, never as part of
the command line, so quotes and symbols in it cannot change what runs.
"""

from __future__ import annotations

import os
import subprocess

MAX_CHARS = 4000
_SCRIPT = (
    "Add-Type -AssemblyName System.Speech; "
    "$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
    "$voice.Speak($env:VOXSCRIBE_SPEAK)"
)
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_process: subprocess.Popen | None = None


def stop() -> None:
    """Stops what is being read, if anything."""
    global _process
    process, _process = _process, None
    if process is not None and process.poll() is None:
        try:
            process.terminate()
        except OSError:
            pass


def is_speaking() -> bool:
    return _process is not None and _process.poll() is None


def speak(text: str) -> bool:
    """Starts reading `text` (replacing anything still being read). Returns
    False when there is nothing to read or the speech could not start."""
    global _process
    text = text.strip()[:MAX_CHARS]
    stop()
    if not text:
        return False
    try:
        _process = subprocess.Popen(  # noqa: S603
            [
                "powershell.exe", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
                "-Command", _SCRIPT,
            ],
            env={**os.environ, "VOXSCRIBE_SPEAK": text},
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=_NO_WINDOW,
        )
    except OSError:
        _process = None
        return False
    return True
