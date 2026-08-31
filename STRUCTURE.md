# STRUCTURE.md

The file/folder scaffold for VoxScribe — what exists today, plus stubs for roadmap items that are planned but not yet built. See [PRD.md](PRD.md) for why each planned piece exists, [ARCHITECTURE.md](ARCHITECTURE.md) for how the existing pieces work, and [architecture-essential.md](architecture-essential.md) for the condensed version.

## Why this file exists

Before building an individual feature, scaffold its place in the project first: create the folder, the file, a one-line docstring or `TODO` stub — even if the logic inside is empty. An empty `core/sync.py` with a docstring saying what it will own is more useful to the next work session (human or agent) than no file at all, because it fixes the *shape* of the feature (what module owns it, what it's called, where it sits relative to existing code) before any implementation decision gets tangled up with a naming or placement decision. Scope the structure first; fill it in feature by feature after.

When asked to scaffold a new area of this project: create every file/folder listed as "planned" below (even if the file is just a docstring and a `pass`), rather than only creating the one file needed for the immediate task.

## Current structure (built, real)

```
ai voice app/
├── main.py                        # entry point: QApplication, single-instance guard, tray
├── VoxScribe.spec                 # PyInstaller build spec
├── installer.iss                  # Inno Setup installer script
├── requirements.txt               # runtime deps
├── requirements-dev.txt           # + pytest, ruff
├── pyproject.toml                 # ruff config
├── license_signing_key.raw        # Ed25519 PRIVATE key — gitignored, never commit, no recovery if lost
│
├── app/                           # Qt UI layer
│   ├── main_window.py             #   MainWindow: recording flow, hotkey wiring, sidebar nav, settings dialog
│   ├── floating_indicator.py      #   FloatingIndicator: standalone status pill widget
│   ├── version.py                 #   __version__, single source of truth
│   └── icon.ico
│
├── core/                          # pure(r)-logic layer, unit-testable
│   ├── audio_capture.py           #   device-adaptive mic capture + resampling
│   ├── transcribe.py              #   faster-whisper wrapper
│   ├── cleanup.py                 #   regex filler-word/formatting pass
│   ├── snippets.py                #   Pro: trigger => expansion
│   ├── license.py                 #   Pro: offline Ed25519 license verification
│   ├── history.py                 #   JSON-backed dictation history + stats
│   ├── settings.py                #   QSettings-backed app settings
│   ├── focused_window.py          #   ctypes foreground-process detection (app exclusion list)
│   ├── updater.py                 #   GitHub Releases version check + download
│   ├── crash_reporter.py          #   global excepthook -> local log files
│   ├── vad.py                     #   Silero VAD — NOT wired into live flow, reference only
│   └── models/
│       └── silero_vad.onnx        #   gitignored, regenerate via scripts/download_vad_model.py
│
├── scripts/                       # one-off dev/build tooling, not shipped
│   ├── generate_icon.py
│   ├── generate_web_assets.py
│   ├── generate_license_key.py    #   dev-only: mint a Pro key after a sale
│   ├── download_vad_model.py
│   └── sign_release.ps1           #   prepped, blocked on the user owning a code-signing cert
│
├── tests/                         # real pytest suite, CI-enforced
│   ├── test_audio_capture.py
│   ├── test_cleanup.py
│   ├── test_crash_reporter.py
│   ├── test_settings.py
│   └── test_updater.py
│
├── test_*.py                      # (repo root) throwaway manual/visual debug tools, not CI, not the real suite
│
├── docs/                          # landing page + privacy policy, deployed to Vercel
│   ├── index.html
│   ├── privacy.html
│   └── (favicons, og-image, demo webp)
│
├── android/VoxScribeAndroid/       # separate Kotlin/Gradle app — see its own README-ANDROID.md
│   ├── release.keystore           #   PRIVATE, gitignored, no recovery if lost
│   ├── keystore.properties        #   PRIVATE, gitignored
│   └── app/                       #   IME + floating-bubble + DictationEngine + WhisperEngine
│
├── .github/workflows/ci.yml       # lint + test + PyInstaller build-check
├── PRD.md / ARCHITECTURE.md / architecture-essential.md / AGENTS.md / CLAUDE.md / README.md
└── (build/dist/installer_output/venv — all gitignored, generated)
```

## Planned structure (not yet built — scaffold these when work on them starts)

Roadmap items from [PRD.md](PRD.md#should-have-partially-built-gated-behind-pro--not-yet-sellable) and [PRD.md](PRD.md#could-have-discussed-not-built), given a real home in the tree ahead of implementation:

```
ai voice app/
├── storefront/                              # NEW — Gumroad-based purchase flow
│   ├── README.md                            #   how the manual flow works today; automation plan
│   └── webhook/                             #   Vercel Function, triggered by Gumroad's sale webhook
│       ├── api/
│       │   └── gumroad-sale.ts              #   receives the webhook, calls the keygen logic, emails the key
│       ├── package.json
│       └── vercel.json
│
├── core/
│   ├── sync.py                               # NEW — cross-device sync client (deferred until Pro has paying users)
│   │                                          #   Planned shape: Supabase client init, device pairing, upload/pull
│   │                                          #   of history+settings, client-side encryption before upload.
│   │                                          #   Deliberately not started — see PRD.md "Could have".
│   └── snippets_variables.py                 # NEW — {date}/{time}/{clipboard} template expansion for Snippets
│                                              #   Planned shape: a small resolver called from snippets.py's
│                                              #   expand() right before the typed-text handoff.
│
├── docs/
│   └── pro.html                              # NEW — a real Pro/pricing landing section once storefront exists
│                                              #   (currently Pro isn't mentioned publicly — no way to buy yet)
│
└── android/VoxScribeAndroid/app/src/main/java/.../sync/   # NEW — Android counterpart to core/sync.py, once built
```

### Scaffold checklist when starting each planned item

- **Gumroad webhook automation** — create `storefront/webhook/` with a stub `api/gumroad-sale.ts` (empty handler + a comment describing the expected Gumroad payload shape) before wiring real logic. This is the natural next step once manual key delivery becomes annoying, per the existing note in [PRD.md](PRD.md).
- **Cross-device sync** — create `core/sync.py` as a stub (docstring only, no Supabase calls yet) the moment this is greenlit, so the module boundary is decided before the Supabase schema is. Pair with a matching Android package stub so both platforms agree on the shape early.
- **Snippet template variables** — create `core/snippets_variables.py` as a stub even before deciding which variables ship first; keeps the resolver's seam separate from `snippets.py`'s trigger-matching logic.
- **Pro storefront page** — create `docs/pro.html` as a bare page (headline + "coming soon") the moment Gumroad is live, rather than only writing it once the full page design is ready.

## Data models (current, real)

These aren't a separate `models/` package — they're plain dataclasses/dicts living next to the logic that owns them. Documented here so their shape is visible without reading every file.

| Model | Lives in | Shape |
|---|---|---|
| History entry | `core/history.py` | `{timestamp, text, word_count, duration_seconds}` — one per dictation, JSON array in `%LOCALAPPDATA%\VoxScribe\history.json` |
| Stats | `core/history.py`'s `compute_stats()` | derived, not stored: `{total_words, avg_wpm, day_streak}` |
| License key | `core/license.py` | `base32(license_id[8 bytes] || ed25519_signature[64 bytes])`, dash-grouped string |
| Snippet | `core/snippets.py` | `{trigger: str, expansion: str}`, one per line in Settings, `trigger => expansion` text format |
| Settings | `core/settings.py` | QSettings key/value pairs (hotkey, mic device id, language, model size, toggles) — not a JSON blob |

### Planned data models (shape not finalized — decide before writing sync.py)

| Model | Would live in | Open questions |
|---|---|---|
| Sync device record | `core/sync.py` | pairing token format, per-device vs. per-account scoping |
| Synced history/settings payload | `core/sync.py` | what's encrypted client-side vs. left as Supabase RLS-protected plaintext |
| Snippet variable | `core/snippets_variables.py` | fixed built-in set (`{date}`, `{time}`, `{clipboard}`) vs. user-extensible |
