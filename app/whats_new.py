"""Changelog text shown once in-app after an update, so users who never
read GitHub release notes still find out what changed. Deliberately a
small hardcoded dict, not fetched from the GitHub API -- this has to work
fully offline, consistent with the rest of the app (see AGENTS.md's "no
cloud calls" note), and the text only needs to exist for versions someone
could realistically be upgrading from.
"""

from __future__ import annotations

WHATS_NEW: dict[str, str] = {
    "1.8.1": (
        "- New: Try harder. A word came out wrong? Press F8 within 2 minutes and the "
        "same recording is run again through a bigger model, and only what changed "
        "is retyped. Free uses Small; Pro uses Large turbo, Large or Medium; with no "
        "bigger model, the one in use runs again in careful mode. Change "
        "the key in Settings.\n"
        "- New: dictation modes. Chat, Email, Code and Notes tidy your words to fit "
        "what you write. With Pro, the mode switches by itself with the app.\n"
        "- New: one Pro key now covers two PCs and two phones, and Remove license "
        "frees this PC so the key can move to a new one.\n"
        "- New: the recording pill shows a live mic level while you talk, so you "
        "can see the microphone is really hearing you.\n"
        "- New: a small animation while your words are being transcribed.\n"
        "- New: a check mark when the text is typed, and a short shake with the "
        "reason when it isn't (no speech heard, window changed, nothing to undo).\n"
        "- New: the pill slides in and fades out instead of popping.\n"
        "- New: the first-run model download has a progress bar, and batch "
        "imports move smoothly.\n"
        "- New: a redesigned Insights page with typing time saved, your speaking "
        "speed against typing, this week's chart, a 12 week activity grid and "
        "highlights. The numbers count up, and a new dictation fades into the "
        "Today list.\n"
        "- New: VoxScribe never types into a password box, in browsers and apps, "
        "and keeps what was said there out of the history.\n"
        "- New: a short welcome with a demo on first launch, also in the tray menu "
        "under How to use VoxScribe.\n"
        "- Safer updates: a downloaded update must match GitHub's checksum before "
        "it is offered to run.\n"
        "- Animations follow the Windows \"Show animations\" setting."
    ),
    "1.8.0": (
        "- New: change what you just dictated by voice. Say \"capitalize that\", "
        "\"all caps\", \"lowercase that\" or \"replace noon with one\", on its own "
        "or at the end of the same sentence.\n"
        "- New: say \"send it\" to press Enter, for example to send a chat message. "
        "Off until you turn it on in Settings, Text.\n"
        "- New: right-click a word in the transcript and pick \"Always correct\" to "
        "add a word replacement.\n"
        "- New: export and import your vocabulary and replacements as one file, "
        "for a backup, another PC or the Android app.\n"
        "- New: the speech models have plain names (Fast, Balanced, Most "
        "accurate), and Large turbo is added for Pro: close to Large, but quicker.\n"
        "- Fixed: a spoken command said right after a long dictation now waits for "
        "the typing to finish."
    ),
    "1.7.2": (
        "- Fixed: importing a file never replaces an existing .srt, .vtt, .md or "
        ".docx any more. A hand corrected caption file is kept and the new one is "
        "saved as \"name (2)\".\n"
        "- New: after a batch there is a report of every file, which failed and "
        "where each .srt went, and a button to retry just the failed ones.\n"
        "- New: caption cards are timed from the words, so each appears when its "
        "first word is spoken and leaves soon after the last, and cards are cut at "
        "pauses. Cards that are too fast, overlap, follow a long silence or stay "
        "on screen too long are flagged for review. Nothing is changed for you.\n"
        "- New: the Dictation page is reorganised so everything fits on one screen. "
        "A batch now always saves a .srt for each file."
    ),
    "1.7.1": (
        "- New: imported captions are split into cards of two lines of 42 "
        "characters (Settings, Files).\n"
        "- New (Pro): import a whole folder, or drop files and folders onto the "
        "window, with progress per file, pause and cancel, and a summary with an "
        "Open folder button. Free users get 2 batch runs to try it; importing one "
        "file is always free."
    ),
    "1.7.0": (
        "- New: Settings is now a full page instead of a box, with sections for "
        "General, Audio, Text, Pro, Files, Privacy and About.\n"
        "- Changes are saved with Save changes; Cancel leaves everything as it was."
    ),
    "1.6.9": (
        "- New (Pro): code dictation. Say \"camel case user name\" to type userName, "
        "or use snake, pascal, kebab and constant case and spoken symbols.\n"
        "- New (Pro): fill-in templates. Say \"template bug report\" and answer each "
        "part by voice.\n"
        "- New (Pro): smart formatting for spoken emails, web addresses and numbers.\n"
        "- New (Pro): a second hotkey that dictates in a second language.\n"
        "- New (Pro): per-app profiles, so code, cleanup and language can differ "
        "by program.\n"
        "- New (Pro): learn your vocabulary from a folder of your own files, on "
        "this PC only.\n"
        "- New (Pro): offline mode blocks all network use, with a log of every "
        "outside connection VoxScribe has tried.\n"
        "- New (Pro): importing a file can also save .vtt, .md and Word copies, "
        "and label who is speaking (a one-time 35 MB download).\n"
        "- New: the Android app can use the same Pro key."
    ),
    "1.6.8": (
        "- Fixed: if the window you dictated into closes or changes before the "
        "text is ready, VoxScribe now holds the text instead of typing it "
        "somewhere else. Click the notification to copy it.\n"
        "- Fixed: a download of an update that was cut short is now detected and "
        "reported instead of leaving a broken installer.\n"
        "- Fixed: \"5 p.m. and then\" and similar abbreviations no longer get a "
        "capital letter after them.\n"
        "- Fixed: clicking an unrelated tray notification no longer starts an "
        "update.\n"
        "- Fixed: the hotkey can no longer stop a recording you started with the "
        "button.\n"
        "- Fixed: if your microphone disconnects while you are recording, the "
        "window no longer gets stuck on Recording.\n"
        "- Fixed: importing several files in a row is more stable."
    ),
    "1.6.7": (
        "- Fixed: scrolling the Settings page no longer changes dropdown values "
        "by accident.\n"
        "- Fixed: a model file that is briefly locked (often by antivirus right "
        "after the download) is now retried before VoxScribe deletes and "
        "re-downloads it.\n"
        "- New: when an update is available it now stays in the tray menu and "
        "the tray tooltip changes, instead of one short notification that is "
        "easy to miss.\n"
        "- New: softer start and stop sounds, if you have sounds turned on in "
        "Settings.\n"
        "- New: adjustable typing delay in Settings, for editors that scramble "
        "or drop characters.\n"
        "- Better: Settings now spells out what Pro adds.\n"
        "- Better: the first letter after every sentence end is capitalized."
    ),
    "1.6.6": (
        "- Fixed: if the speech model download was broken, VoxScribe now repairs it "
        "automatically and shows a clear message with a Retry button instead of "
        "sitting on \"Loading model\".\n"
        "- Fixed: first-run model downloads now show their progress.\n"
        "- Fixed: silent or empty recordings no longer produce made-up text or an error.\n"
        "- Fixed: cleanup no longer removes real repeated words like \"had had\" or \"bye bye\".\n"
        "- Fixed: long dictations no longer freeze the window while typing, and dictating "
        "during a file import is blocked instead of risking a crash.\n"
        "- Fixed: \"scratch that\" only ever deletes in the window the text was typed into.\n"
        "- New: you can turn off the anonymous launch ping in Settings."
    ),
    "1.6.5": (
        "- New: Word replacements in Settings. Fix words Whisper keeps mishearing "
        "(for example \"vox scribe\" to \"VoxScribe\").\n"
        "- New: \"Keep microphone ready\" (off by default) so your first word is "
        "never clipped.\n"
        "- New: Left Shift is now a hotkey option. Hold it alone for a moment to "
        "talk; normal typing never triggers it."
    ),
    "1.6.4.1": (
        "- Settings now shows a direct \"Get Pro\" button and a quick price "
        "comparison, so upgrading doesn't require hunting for a link."
    ),
    "1.6.4": (
        "- New: Import Audio lets you transcribe existing audio/video files "
        "(wav, mp3, m4a, mp4, mov, flac, and more), not just live dictation. "
        "Pick multiple files at once to transcribe them in one batch.\n"
        "- New: Translate to English (opt-in in Settings) outputs English text "
        "regardless of the language you spoke in.\n"
        "- New: optionally save a .srt caption file alongside an imported "
        "audio/video file, with real timestamps."
    ),
    "1.6.3.2": (
        "- New: say \"delete last word\" or \"delete last sentence\" to remove just "
        "that much of your last dictation (with Voice commands enabled in Settings)."
    ),
    "1.6.3.1": (
        "- New: say \"scratch that\" alone to undo the last thing VoxScribe typed "
        "(with Voice commands enabled in Settings).\n"
        "- Real icons throughout the app, replacing the old hand-drawn ones."
    ),
    "1.6.3": (
        "- New look: green waveform icon and accent color throughout the app.\n"
        "- Fixed: the Settings window could overflow and clip its fields on some "
        "displays."
    ),
    "1.6.2": (
        "- Voice commands (opt-in): say \"period\", \"comma\", \"new line\" and more "
        "while dictating to get real punctuation instead of the literal words. "
        "Off by default in Settings.\n"
        "- Fixed: dictated text could type into the wrong window if you switched "
        "apps while a transcription was still finishing."
    ),
}


def whats_new_text(version: str) -> str | None:
    return WHATS_NEW.get(version)
