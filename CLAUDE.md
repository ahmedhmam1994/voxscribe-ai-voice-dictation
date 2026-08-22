# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

VoxScribe: a Windows desktop voice-to-text dictation app (Python + PySide6). Hold a global hotkey (F9 by default, user-changeable via the tray menu) anywhere on the system, talk, release — the audio is transcribed locally via faster-whisper and typed directly into whatever window currently has focus. Modeled after Wispr Flow. Runs from the system tray; no main window is required for normal use.

## Commands

All commands run from the project root with the venv activated (`venv\Scripts\python.exe` on Windows).

```
venv\Scripts\python.exe main.py                          # run the app
venv\Scripts\python.exe -m PyInstaller --noconfirm --clean VoxScribe.spec   # build the standalone .exe -> dist\VoxScribe\
"C:\Users\<user>\AppData\Local\Programs\Inno Setup 6\ISCC.exe" installer.iss  # build the installer -> installer_output\VoxScribe-Setup.exe (requires the exe already built)
venv\Scripts\python.exe scripts\generate_icon.py          # regenerate app\icon.ico
venv\Scripts\python.exe scripts\download_vad_model.py     # re-download core\models\silero_vad.onnx if missing

venv\Scripts\pip install -r requirements-dev.txt          # install pytest + ruff on top of runtime deps
venv\Scripts\python.exe -m pytest tests/ -v                # run the real automated test suite (core/cleanup.py, core/updater.py, core/audio_capture.py, core/crash_reporter.py)
venv\Scripts\python.exe -m ruff check .                    # lint (config in pyproject.toml; excludes the throwaway test_*.py scripts below)
```

CI (`.github/workflows/ci.yml`) runs lint + tests + a PyInstaller build-check on every push/PR to `main`, on `windows-latest` (this app is Windows-specific, so a Linux runner wouldn't exercise the real import graph).

Automated tests live in `tests/` (pytest) and cover the pure-logic modules: `core/cleanup.py`, `core/updater.py`'s version comparison, `core/audio_capture.py`'s resampling, and `core/crash_reporter.py`. They deliberately don't cover the Qt/audio/Whisper integration itself. The standalone `test_*.py` scripts at the project root are a separate, older thing — throwaway manual/visual test tools, not part of the shipped app and not run in CI — kept for hands-on debugging (mic levels, VAD tuning) rather than as regression tests.

## Architecture

**Entry point**: `main.py` constructs `QApplication` and `MainWindow`, then starts hidden — no `window.show()` call. The app is tray-first: `MainWindow._setup_tray_icon()` creates the `QSystemTrayIcon`, and `closeEvent` hides the window instead of quitting (`QApplication.setQuitOnLastWindowClosed(False)` reinforces this). Real exit only happens via the tray menu's Quit (`_quit_app`, which calls `keyboard.unhook_all()` before `QApplication.quit()`).

**Recording flow** (`app/main_window.py`): two independent trigger paths converge on the same `_start_recording`/`_stop_recording` methods:
- The on-screen Start/Stop button (`toggle_recording`) — plain toggle.
- The global hotkey — **hold-to-talk**, not toggle. Registered via `keyboard.on_press_key`/`on_release_key` (not `add_hotkey`), because `keyboard`'s callbacks fire on a non-Qt background thread. `HotkeyBridge(QObject)` re-emits them as Qt signals so Qt's cross-thread auto-queuing safely delivers them to the main thread. `_hotkey_key_down` guards against key-repeat re-triggering a start; `_hotkey_active_session` ensures a hotkey-released event only stops a recording the hotkey itself started (not one started by the button). The key itself is user-configurable (`core/settings.py`, QSettings-backed, tray menu's "Change Hotkey..." → `MainWindow._open_hotkey_dialog`) but deliberately curated to F-keys and a few rarely-typed keys (`AVAILABLE_HOTKEYS`) rather than free entry — since this is a *global* hook, landing it on a normal typing key would break typing that key everywhere while VoxScribe runs. `MainWindow._register_global_hotkey` unhooks the previous key and re-registers on change; note `keyboard.unhook()` on the second (release) hook of a pair can raise `KeyError` since the library's internal registry is keyed by key name, not hook identity — caught deliberately, not a bug.

**Audio capture is device-adaptive, not hardcoded to 16kHz** (`core/audio_capture.py`): `_default_input_device()` deliberately resolves the WASAPI host API's default input device rather than sounddevice's generic default — on this project's target hardware, the generic default landed on an MME driver that produced near-silent audio for a Bluetooth headset. Recording opens at the device's own native sample rate (`device_native_samplerate`), not a forced 16kHz, because forcing 16kHz on some devices/drivers raises `PortAudioError: Invalid sample rate` (observed when falling back to a laptop's internal mic at 48kHz). `resample_to_16k()` converts the captured buffer to 16kHz afterward for Whisper. When touching mic capture, preserve this device-selection + native-rate + resample pattern — it's a deliberate fix for real hardware failures, not incidental.

**Transcription** (`core/transcribe.py`): `Transcriber` wraps `faster_whisper.WhisperModel` (currently `"small"`, CPU, `compute_type="int8"`; `vad_filter=True` lets faster-whisper's own bundled VAD trim silence within a clip). Before transcribing, audio is peak-normalized (`transcribe()`'s `peak` scaling) — recording hardware here has been quiet enough that this materially affects accuracy. Model loading and each transcription run on separate `QThread`s (`ModelLoaderThread`, `TranscribeThread` in `main_window.py`) so the Qt event loop never blocks.

**Text cleanup** (`core/cleanup.py`): `clean_transcript()` is a regex-based filler-word/formatting pass (strips "um"/"uh"/"you know", a comma-bounded heuristic for filler "like", collapses repeated words, fixes spacing/capitalization) — intentionally not an LLM call, to avoid any API cost. Runs on every transcription result before it's displayed or typed.

**Delivery into other apps**: after transcription + cleanup, `_type_into_focused_window` calls `keyboard.write(text, delay=0.012)` to simulate typing directly into whichever window has focus — deliberately not clipboard+paste (would clobber the user's clipboard). The small per-character delay is required: rich-text/JS-driven inputs (e.g. web-based chat boxes) can scramble character order if keystrokes are injected faster than they can process them.

**`core/vad.py` (Silero VAD via onnxruntime) is present but not used by the live app flow.** It was the original design (auto-detect speech in a continuous stream) but proved unreliable on quiet/variable Bluetooth mic input — real speech sometimes produced classifier probabilities too low/inconsistent to trust as a start/stop trigger, and false triggers caused Whisper to hallucinate text from noise. The project moved to explicit hold-to-talk instead. Kept for reference/possible future use; don't assume it's wired into the main window. The `core/models/silero_vad.onnx` model file is git-ignored — regenerate with `scripts/download_vad_model.py`.

**`app/floating_indicator.py`**: `FloatingIndicator` is a separate frameless/always-on-top/translucent widget (not part of `MainWindow`'s layout) that shows a small status pill during recording/transcribing, positioned bottom-center of the primary screen. Shown/hidden via `show_status()`/`hide_indicator()`, called from the same points in `main_window.py` that drive the status label.

**Packaging**: `VoxScribe.spec` is a PyInstaller spec using `collect_all()` for the heavy/dynamic-import-heavy dependencies (PySide6, faster_whisper, ctranslate2, onnxruntime, av, tokenizers, huggingface_hub, keyboard) rather than relying on PyInstaller's default import scanning, which misses these. `console=False` and `icon='app/icon.ico'` are set for a real end-user app (no terminal window). The Whisper model itself is **not** bundled — it downloads to the user's Hugging Face cache on first run, so first launch needs internet. `installer.iss` (Inno Setup) wraps `dist\VoxScribe\` into a single-file installer; it must be rebuilt after any PyInstaller rebuild since it packages `dist\VoxScribe\*` directly.
