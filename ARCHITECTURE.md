# ARCHITECTURE.md

Full architecture reference for VoxScribe. For a condensed version scoped to what an agent needs before making a change, see [architecture-essential.md](architecture-essential.md). For product requirements, see [PRD.md](PRD.md). For commands and dev-workflow rules, see [CLAUDE.md](CLAUDE.md).

## System overview

VoxScribe is a Windows desktop app (Python + PySide6) plus a separate Android app (Kotlin). They share a product concept — hold to talk, release to get transcribed text typed into the focused field — but are independent codebases with independent speech-to-text stacks (faster-whisper on desktop, sherpa-onnx-bundled Whisper or Android's `SpeechRecognizer` on Android). This document covers the desktop app in depth and the Android app at a summary level.

## Desktop app

### Entry point and process model

`main.py` constructs `QApplication` and `MainWindow`, then starts hidden — no `window.show()` call. The app is tray-first:
- `MainWindow._setup_tray_icon()` creates the `QSystemTrayIcon`.
- `closeEvent` hides the window instead of quitting (`QApplication.setQuitOnLastWindowClosed(False)` reinforces this).
- Real exit only happens via the tray menu's Quit (`_quit_app`), which calls `keyboard.unhook_all()` before `QApplication.quit()`.
- A `QSharedMemory`-based single-instance guard prevents a second launch: without it, two processes each hold the global hotkey hook, and every keypress causes both to record/transcribe/type concurrently — this produced real garbled/doubled text in production (see the v1.2 bugfix in the project history) and is now structurally prevented rather than left as a "remember to Quit properly" convention.

### Recording flow

Two independent trigger paths converge on the same `_start_recording`/`_stop_recording` methods in `app/main_window.py`:

- **The on-screen Start/Stop button** (`toggle_recording`) — a plain toggle.
- **The global hotkey** — **hold-to-talk, not toggle.** Registered via `keyboard.on_press_key`/`on_release_key` (not `add_hotkey`), because the `keyboard` library's callbacks fire on a non-Qt background thread. `HotkeyBridge(QObject)` re-emits them as Qt signals so Qt's cross-thread auto-queuing safely delivers them to the main thread.
  - `_hotkey_key_down` guards against key-repeat re-triggering a start.
  - `_hotkey_active_session` ensures a hotkey-released event only stops a recording the hotkey itself started (not one started by the button).
  - The key is user-configurable (`core/settings.py`, QSettings-backed; tray menu's "Change Hotkey..." → `MainWindow._open_hotkey_dialog`) but deliberately curated to F-keys and a few rarely-typed keys (`AVAILABLE_HOTKEYS`) rather than free entry, since this is a *global* hook — landing it on a normal typing key would break typing that key everywhere while VoxScribe runs.
  - `MainWindow._register_global_hotkey` unhooks the previous key and re-registers on change. Note: `keyboard.unhook()` on the second (release) hook of a pair can raise `KeyError` since the library's internal registry is keyed by key name, not hook identity — this is caught deliberately, not a latent bug.

### Audio capture — device-adaptive, not hardcoded

`core/audio_capture.py` deliberately does not assume a fixed 16kHz stream or a fixed default device:

- `_default_input_device()` resolves the WASAPI host API's default input device rather than sounddevice's generic default. On the target hardware, the generic default landed on an MME driver that produced near-silent audio for a Bluetooth headset.
- Recording opens at the device's own native sample rate (`device_native_samplerate`), not a forced 16kHz — forcing 16kHz on some devices/drivers raises `PortAudioError: Invalid sample rate` (observed falling back to a laptop's internal mic at 48kHz).
- `resample_to_16k()` converts the captured buffer to 16kHz afterward for Whisper.
- `sd.InputStream()` creation is wrapped in try/except so a machine with no microphone shows a UI error instead of crashing.
- `list_input_devices()` / `resolve_input_device()` back the Settings microphone picker, falling back to auto-detect if the chosen device is unplugged.

**When touching mic capture, preserve this device-selection + native-rate + resample pattern** — it is a deliberate fix for real hardware failures on real devices, not incidental complexity.

### Transcription

`core/transcribe.py`'s `Transcriber` wraps `faster_whisper.WhisperModel` (model size user-selectable — tiny/base/small — CPU, `compute_type="int8"`; `vad_filter=True` lets faster-whisper's own bundled VAD trim silence within a clip, distinct from the standalone `core/vad.py` described below).

- Audio is peak-normalized before transcription (`transcribe()`'s `peak` scaling) — the recording hardware in use has been quiet enough that this materially affects accuracy.
- The Whisper model is multilingual (~100 languages) — dictation language is a user setting (`language="en"` was originally hardcoded; exposing it required zero extra download).
- `initial_prompt` carries the user's custom-vocabulary setting as a hint to the model — the local equivalent of a cloud dictation tool's custom dictionary.
- Model loading and each transcription run on separate `QThread`s (`ModelLoaderThread`, `TranscribeThread` in `main_window.py`) so the Qt event loop never blocks.

### Post-processing pipeline

After transcription, in order:

1. **Cleanup** (`core/cleanup.py`) — `clean_transcript()` is a regex-based filler-word/formatting pass (strips "um"/"uh"/"you know", a comma-bounded heuristic for filler "like", collapses repeated words, fixes spacing/capitalization). Intentionally not an LLM call, to keep the product at zero incremental cost and keep transcription fully local. User-toggleable.
2. **Snippets** (`core/snippets.py`, Pro-gated) — expands `trigger => expansion` pairs the user has defined; applied after cleanup, before typing/history/stats. Gated behind `core.license.is_pro()` both in the UI (grayed out when free) and in the actual pipeline.
3. **History + stats recording** (`core/history.py`) — JSON-backed dictation history (`%LOCALAPPDATA%\VoxScribe\history.json`): timestamp, text, word count, duration per entry. `compute_stats()` derives total words, average WPM (from actual recording duration), and current day-streak. Written alongside the pre-existing running counters in `core/settings.py`.
4. **Typing into the focused window** — `_type_into_focused_window` calls `keyboard.write(text, delay=0.03)` to simulate typing directly into whichever window has focus. Deliberately not clipboard+paste (would clobber the user's clipboard). The per-character delay is required: rich-text/JS-driven inputs (e.g. web-based chat boxes) can scramble character order if keystrokes are injected faster than they can be processed. (Delay was bumped 12ms → 30ms while investigating a real garbled-text bug that turned out to actually be caused by the dual-process race described above — the delay bump is a real, if minor, robustness improvement kept regardless.)

`core/focused_window.py` (pure-ctypes, no pywin32 dependency) does foreground-process detection, backing the app-exclusion-list setting (won't record while e.g. a password manager is focused).

### Voice activity detection — not used live

`core/vad.py` (Silero VAD via onnxruntime) is present but **not wired into the live app flow**. It was the original design (auto-detect speech in a continuous stream) but proved unreliable on quiet/variable Bluetooth mic input: real speech sometimes produced classifier probabilities too low/inconsistent to trust as a start/stop trigger, and false triggers caused Whisper to hallucinate text from noise. The project moved to explicit hold-to-talk instead. Kept for reference/possible future use — don't assume it's wired in. `core/models/silero_vad.onnx` is git-ignored; regenerate with `scripts/download_vad_model.py`.

### UI shell

- `app/main_window.py` — `MainWindow`, sidebar-navigated (`QStackedWidget`): Dictation / Insights / Settings pages (dashboard-shell redesign, 2026-08-22 — see status note history). Dictation page has the record button, transcript view, and a "Today" history feed. Insights page has stat cards (total words / avg WPM / day streak).
- `app/floating_indicator.py` — `FloatingIndicator`, a separate frameless/always-on-top/translucent widget (not part of `MainWindow`'s layout) showing a small status pill during recording/transcribing, positioned bottom-center of the primary screen. Shown/hidden via `show_status()`/`hide_indicator()`, called from the same points in `main_window.py` that drive the status label.
- Vector icons are hand-drawn via `QPainter` (no new dependency) rather than bitmap assets — mic/stop swap on the record button plus save/copy/clear/keyboard/settings/globe icons.
- Styling is QSS (`SETTINGS_DIALOG_STYLESHEET` etc.) — see [Open decision: UI/framework ceiling](#open-decision-uiframework-ceiling) below for the known limits of this approach.

### Licensing (VoxScribe Pro)

`core/license.py` — offline Pro-license verification via **Ed25519 signatures**. A license key is `base32(license_id[8 bytes] || signature[64 bytes])`, dash-grouped for readability.

- Verification needs no network call and no account — the Ed25519 **public** key is embedded in the shipped app.
- The matching **private** key lives only in `license_signing_key.raw` at the repo root — **gitignored, never committed.** Losing it means no new keys can ever be issued (already-sold keys stay valid, since verification is offline and only needs the public key); leaking it means anyone can forge a valid key. This is a critical secret requiring backup outside the repo, same criticality class as the Android release keystore below.
- `scripts/generate_license_key.py` is the dev-only tool to mint a new key after a sale, reading the private key file.

### Reliability, trust, and distribution

- **Single-instance guard** (`QSharedMemory`, `main.py`) — see Process model above.
- **Crash logging** (`core/crash_reporter.py`) — a global `sys.excepthook` writes uncaught exceptions to `%LOCALAPPDATA%\VoxScribe\logs\`. Nothing is auto-uploaded, consistent with the no-telemetry privacy positioning. A "Open Logs Folder" tray item exposes this to the user directly.
- **Auto-update check** (`core/updater.py`) — checks GitHub Releases on startup and every 7 days while the app runs in the tray; surfaced via a tray notification, notify-only (never silent download/install — judged too risky at this project's scale to overwrite a running `.exe` and handle elevation). A "Check for Updates..." tray item and a one-click in-app download (`UpdateDownloadThread`) exist, but running the downloaded installer is still an explicit second click by design.
- **Code signing** — scripted (`scripts/sign_release.ps1`) but not completed; blocked on the user purchasing an OV/EV certificate or setting up Microsoft Trusted Signing. Until then, Windows SmartScreen shows a warning on install, documented in the README/landing page rather than hidden.
- **Version source of truth** — `app/version.py`'s `__version__` is imported by both the updater and the crash reporter. `installer.iss`'s `MyAppVersion` is compiled separately by Inno Setup and **must be bumped by hand** alongside it — there is no automated link between the two.
- **CI** (`.github/workflows/ci.yml`) — lint (ruff) + pytest on every push/PR to `main`, plus a `build-check` job that runs a real PyInstaller build and fails if `dist\VoxScribe\VoxScribe.exe` isn't produced. Runs on `windows-latest` deliberately (not Linux), since the app's own import graph is Windows-specific (WASAPI queries, `os.startfile`, the `keyboard` library's global-hook path).
- **Tests** (`tests/`, pytest) cover the pure-logic modules only: `core/cleanup.py`, `core/updater.py`'s version comparison, `core/audio_capture.py`'s resampling math, `core/crash_reporter.py`'s log-file writing. They deliberately don't cover the Qt/audio/Whisper integration itself. The standalone `test_*.py` scripts at the project root are a separate, older thing — throwaway manual/visual test tools (mic levels, VAD tuning), not part of the shipped app, not run in CI, and excluded from ruff's lint scope.

### Packaging

- `VoxScribe.spec` (PyInstaller) uses `collect_all()` for heavy/dynamic-import-heavy dependencies (PySide6, faster_whisper, ctranslate2, onnxruntime, av, tokenizers, huggingface_hub, keyboard) rather than relying on PyInstaller's default import scanning, which misses these. `console=False`, `icon='app/icon.ico'`.
- The Whisper model itself is **not** bundled — it downloads to the user's Hugging Face cache on first run, so first launch needs internet. ("Offline/no cloud" in marketing copy is intentionally precise about this: transcription itself is 100% local; the model download is a one-time exception.)
- `installer.iss` (Inno Setup) wraps `dist\VoxScribe\` into a single-file installer. It must be rebuilt after any PyInstaller rebuild since it packages `dist\VoxScribe\*` directly, and its version string must be bumped by hand (see above).
- Distributed as a GitHub Release asset (`VoxScribe-Setup.exe`, ~83MB as of v1.4), not committed to the repo and not served via GitHub Pages — Releases support assets up to 2GB, which is the right home for a binary this size.

### Open decision: UI/framework ceiling

PySide6/QSS has a real design ceiling — no CSS transitions, weak gradient/shadow control — that has already produced multiple real Qt-default-styling bugs (unstyled `QScrollArea` viewports, unstyled `QTextEdit`, unstyled tray/dropdown menus, all fixed reactively as found). Five paths were compared: stay on QSS, move to QML (same PySide6 backend, different UI layer), embed `QWebEngineView` (real CSS, but reintroduces the WebEngine bundle size that v1.3 deliberately removed to shrink the installer 229MB→77MB), a full Electron/Tauri rewrite, or Flutter. **QML was recommended** (same backend, real ceiling raise, no installer regression, lowest risk) but **the decision was not made or actioned** — confirm current direction with the user before doing further deep UI work rather than assuming QML was chosen.

## Android app (`android/VoxScribeAndroid/`)

Summary only — this is a separate Kotlin/Gradle codebase with its own build system, not covered by the desktop app's CLAUDE.md commands.

- **Not a global-hotkey app** — Android deliberately blocks apps from grabbing global hotkeys that inject text into an arbitrary focused app. Instead, two interaction modes:
  - **Custom keyboard (IME)** — switch to VoxScribe in the keyboard picker, hold the mic button, talk, release.
  - **Floating bubble** — a drag-anywhere overlay (`BubbleService`, `AccessibilityService`-based), the same approach Wispr Flow itself uses on Android. All 6 build phases complete and verified on real hardware (permissions/scaffolding, bubble UI, accessibility text insertion, shared transcription engine, onboarding UI, device-verification pass).
- **Speech-to-text**: two engines behind a common interface —
  - Android's built-in `SpeechRecognizer` with `EXTRA_PREFER_OFFLINE=true` (zero native build steps, depends on the device having Google's offline voice-typing language pack).
  - Bundled on-device Whisper via [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) (`WhisperEngine`), the real match to the desktop app's faster-whisper. Currently the multilingual `base` model (~160MB) for accent/dialect robustness at a still-practical size. `WhisperEngine.isAvailable()` fails closed to the `SpeechRecognizer` fallback if model assets are missing or fail to load.
- **`DictationEngine.kt`** is the shared recording/transcription/cleanup pipeline extracted out of the IME so both the keyboard and the floating bubble drive the same code path.
- **`VoxScribeAccessibilityService`** inserts text via `ACTION_SET_TEXT` at the tracked cursor/selection, with a clipboard+`ACTION_PASTE` fallback for fields that don't support direct text-setting (some WebViews) — the one deliberate exception to the "never touch the clipboard" principle on this project, with the previous clipboard content restored immediately after.
- **Signing**: a real release keystore (`release.keystore`, PKCS12) exists, gitignored, required for any future Play Store update to the same listing. **Losing it or its password (`keystore.properties`) permanently blocks future updates to that listing** — the user must back both up outside the repo. This is the Android-side equivalent of the desktop license signing key's criticality.
- **Play Store publishing** is prepped (signing config, privacy policy at `docs/privacy.html`) but not submitted — requires the user's own Google Play Console developer account and a closed-testing period, both non-delegable.

## Cross-cutting notes for future work

- **Dev-environment file-path quirk**: `venv\Scripts\python.exe` in this environment is the Microsoft Store build of Python 3.13, which virtualizes `%LOCALAPPDATA%` writes into a `Packages\...\LocalCache\Local\` path instead of the real one. This only affects the dev loop — the packaged/frozen `.exe` end users run does not go through this virtualization. Worth remembering if `Path.home()`-based file I/O ever looks like it's silently not persisting during local testing.
- **Verifying UI changes in this dev environment is unreliable** — background-launched Qt dev-instance windows here don't reliably attach to a visible desktop session. The dependable way to let the user see a UI change has been to rebuild the packaged app (`PyInstaller` → `ISCC.exe`) and silently reinstall over the running copy (`VoxScribe-Setup.exe /VERYSILENT`), not to try to surface a live dev window.
- **Two secrets require external backup, both single points of failure for future monetization/updates**: `license_signing_key.raw` (Pro licensing) and `android/VoxScribeAndroid/release.keystore` + `keystore.properties` (Play Store updates). Neither is committed to git by design; neither has a recovery path if lost.
