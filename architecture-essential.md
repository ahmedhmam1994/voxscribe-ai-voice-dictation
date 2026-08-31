# architecture-essential.md

Condensed architecture reference — the minimum an agent needs before touching this codebase. Full detail (Android app, packaging, distribution, open decisions, historical rationale) lives in [ARCHITECTURE.md](ARCHITECTURE.md). Product requirements are in [PRD.md](PRD.md). Build/run/test commands are in [CLAUDE.md](CLAUDE.md).

## What this is

VoxScribe: a Windows desktop dictation app. Hold F9 (user-configurable) anywhere on the system, talk, release — audio is transcribed locally (faster-whisper) and typed into whatever window has focus. Tray-first, no main window required. A separate Android companion app exists (`android/VoxScribeAndroid/`, Kotlin) — not covered here.

## The five things that will bite you if you don't know them

1. **Two independent trigger paths share one start/stop pair.** The Start/Stop button (`toggle_recording`) and the global hotkey (hold-to-talk, via `keyboard.on_press_key`/`on_release_key`) both call `_start_recording`/`_stop_recording` in `app/main_window.py`. The hotkey fires on a non-Qt thread — `HotkeyBridge(QObject)` re-emits as Qt signals for thread-safe delivery. `_hotkey_key_down` and `_hotkey_active_session` prevent key-repeat and cross-path stop bugs.

2. **Audio capture is device-adaptive by design, not a shortcut to fix.** `core/audio_capture.py` resolves the WASAPI default input device (not sounddevice's generic default — that picked a broken MME driver on real hardware) and records at the device's *native* sample rate, resampling to 16kHz afterward (`resample_to_16k()`). Forcing 16kHz directly crashes on some devices. **Do not hardcode a sample rate here.**

3. **Single-instance enforcement is load-bearing, not optional.** `main.py` uses `QSharedMemory` to block a second launch. Two instances each hold the global hotkey hook — every keypress then records/transcribes/types twice concurrently, producing garbled interleaved text (a real shipped bug, v1.2). Don't remove or weaken this guard.

4. **`core/vad.py` (Silero VAD) is dead code for the live flow.** It was the original auto-detect design, dropped because it was unreliable on quiet/variable mic input and caused Whisper to hallucinate on false triggers. Hold-to-talk replaced it. Don't assume VAD is wired into `main_window.py`.

5. **Typing uses `keyboard.write()`, never clipboard.** Deliberate — clipboard+paste would clobber the user's clipboard on every dictation. The 30ms per-character delay is required for JS-driven inputs that scramble fast keystroke injection. The one exception anywhere in the product is Android's accessibility-service text insertion, which falls back to clipboard+paste only for fields that don't support direct text-setting, restoring the previous clipboard content immediately after.

## Post-transcription pipeline order

Transcribe → **cleanup** (`core/cleanup.py`, regex-based filler-word removal, not an LLM call) → **snippets** (`core/snippets.py`, Pro-gated trigger expansion) → **history/stats** (`core/history.py`) → **type into focused window**.

## Two secrets, never commit, no recovery if lost

- `license_signing_key.raw` (repo root, gitignored) — Ed25519 private key for VoxScribe Pro license generation. Lost = no new Pro keys ever again.
- `android/VoxScribeAndroid/release.keystore` + `keystore.properties` (gitignored) — Play Store signing. Lost = can never update that Play Store listing again.

## Threading model

Whisper model loading and each transcription run on dedicated `QThread`s (`ModelLoaderThread`, `TranscribeThread`) so the Qt event loop never blocks. Anything long-running added to the recording/transcription path should follow this pattern, not run on the main thread.

## Where things live

| Concern | File |
|---|---|
| Entry point, tray, single-instance | `main.py` |
| Main window, recording flow, hotkey wiring | `app/main_window.py` |
| Floating status pill | `app/floating_indicator.py` |
| Mic capture, resampling | `core/audio_capture.py` |
| Whisper wrapper | `core/transcribe.py` |
| Filler-word cleanup | `core/cleanup.py` |
| Snippets (Pro) | `core/snippets.py` |
| License verification | `core/license.py` |
| Dictation history/stats | `core/history.py` |
| Settings (QSettings-backed) | `core/settings.py` |
| Foreground-app detection (exclusion list) | `core/focused_window.py` |
| Auto-update check | `core/updater.py` |
| Crash logging | `core/crash_reporter.py` |
| Version source of truth | `app/version.py` |
| Unused VAD (reference only) | `core/vad.py` |

## Before making a change

- If touching mic/audio: read the device-adaptive rationale above first — don't "simplify" it back to a fixed sample rate or generic default device.
- If touching the hotkey/recording flow: check both trigger paths (button and hotkey) still converge correctly.
- If adding a Pro feature: gate it in both the UI (grayed out when free) and the actual pipeline, following the `core.license.is_pro()` pattern already used by Snippets.
- If it's a UI-only change and you need to see it rendered: rebuilding the packaged `.exe` and reinstalling has proven more reliable in this dev environment than a live dev-instance window — see `run-voxscribe` skill / [ARCHITECTURE.md](ARCHITECTURE.md#cross-cutting-notes-for-future-work).
