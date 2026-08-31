# AGENTS.md

Instructions for AI coding agents working in this repository. See also [CLAUDE.md](CLAUDE.md) (Claude Code-specific project guidance — the two should stay consistent; this file is the tool-agnostic equivalent), [architecture-essential.md](architecture-essential.md) (condensed architecture, read before touching core recording/audio/hotkey code), [ARCHITECTURE.md](ARCHITECTURE.md) (full detail), and [PRD.md](PRD.md) (product intent).

## Project

VoxScribe: a Windows desktop voice-to-text dictation app (Python + PySide6). Hold a global hotkey, talk, release — audio is transcribed locally via faster-whisper and typed into whatever window has focus. Runs from the system tray. A separate Android companion app lives in `android/VoxScribeAndroid/` (Kotlin/Gradle, own build system).

## Setup

```
venv\Scripts\python.exe main.py                          # run the app (venv must already exist and be populated)
venv\Scripts\pip install -r requirements-dev.txt          # install pytest + ruff on top of runtime deps
```

There is no dependency-install-from-scratch command documented here beyond the dev extras — assume `venv/` is already provisioned unless told otherwise; don't attempt to recreate it without asking.

## Build

```
venv\Scripts\python.exe -m PyInstaller --noconfirm --clean VoxScribe.spec        # -> dist\VoxScribe\
"C:\Users\<user>\AppData\Local\Programs\Inno Setup 6\ISCC.exe" installer.iss     # -> installer_output\VoxScribe-Setup.exe (needs the exe built first)
```

`installer.iss`'s `MyAppVersion` must be bumped by hand alongside `app/version.py`'s `__version__` — they are not linked automatically.

## Test

```
venv\Scripts\python.exe -m pytest tests/ -v
```

Tests cover only the pure-logic modules: `core/cleanup.py`, `core/updater.py`'s version comparison, `core/audio_capture.py`'s resampling, `core/crash_reporter.py`. They deliberately do not cover the Qt/audio/Whisper integration. The standalone `test_*.py` scripts at the repo root are older throwaway manual/visual debugging tools (mic levels, VAD tuning) — not part of the shipped app, not run in CI, don't treat them as the real test suite.

CI (`.github/workflows/ci.yml`) runs lint + tests + a PyInstaller build-check on every push/PR to `main`, on `windows-latest` (the app's import graph is Windows-specific).

## Lint

```
venv\Scripts\python.exe -m ruff check .
```

Config in `pyproject.toml`, pinned to a narrow rule set (E/F/I) rather than ruff's shifting defaults. Excludes the root-level throwaway `test_*.py` scripts.

## Code style

- No comments explaining *what* code does — names should carry that. Comments are reserved for non-obvious *why* (a hidden constraint, a workaround for a specific hardware/library bug, a deliberate rejection of an alternative).
- Don't add abstractions, config flags, or error handling for scenarios that can't happen in this app's real usage. This is a hobby-to-small-business project, not an enterprise codebase — match existing scope.
- Preserve the device-adaptive audio pattern (native sample rate + resample, WASAPI default device resolution) — it exists because of real hardware failures, not by accident. See [architecture-essential.md](architecture-essential.md).

## Before committing / opening a PR

- Run `pytest` and `ruff check` locally — both run in CI and will block a PR.
- If you touched `app/version.py`, also bump `installer.iss`'s `MyAppVersion` by hand.
- If a UI-visible change needs to actually be seen (not just unit-tested), rebuilding the packaged `.exe` and reinstalling (`PyInstaller` → `ISCC.exe` → `VoxScribe-Setup.exe /VERYSILENT`) has proven more reliable in this dev environment than a live dev-instance window.
- Never commit `license_signing_key.raw` (repo root) or `android/VoxScribeAndroid/release.keystore` / `keystore.properties` — both are gitignored on purpose and have no recovery path if leaked or lost. Double-check `git status`/`git diff` before staging if you've touched licensing or Android signing code nearby.
- Two staged-but-uncommitted efforts may exist in the working tree at any given time (VoxScribe Pro licensing/snippets, dashboard-shell UI redesign) — check `git status` before assuming a clean tree, and don't assume uncommitted local changes are stale/abandoned without asking.

## Security notes specific to this repo

- `license_signing_key.raw` and the Android release keystore are the two secrets in this repo with no recovery path. Treat any code path that reads, logs, or transmits them as high-risk.
- No cloud LLM calls exist anywhere in the transcription/cleanup/snippets pipeline by design — this is the product's core privacy claim. Don't introduce one (e.g. for "smarter" cleanup) without an explicit product decision — see [PRD.md](PRD.md#explicitly-out-of-scope).
- No telemetry/analytics beyond purely local, on-device counters (`core/history.py`, `core/settings.py`). Don't add any without an explicit product decision.
