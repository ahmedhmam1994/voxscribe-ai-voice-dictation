# PRD.md

Product requirements for VoxScribe. This is the "why" and "what" companion to [ARCHITECTURE.md](ARCHITECTURE.md) (the "how") and [CLAUDE.md](CLAUDE.md) (dev-facing build/run instructions).

## Problem

Dictation on Windows is either a paid cloud product (Wispr Flow) that sends audio off-device, or Windows' built-in voice typing, which is limited and not app-agnostic in the same "hold a key anywhere, talk, get text" way. There's no free, local-only, privacy-respecting equivalent.

## Product vision

A Windows desktop dictation tool that works like Wispr Flow: hold a global hotkey anywhere on the system, talk, release, and the transcribed text is typed directly into whatever app has focus — with zero cloud dependency for the transcription itself, and zero cost.

## Target user

Primarily the developer/user themself (dogfooded daily), secondarily anyone who wants free, private, offline-capable dictation into any Windows app — writers, developers using AI chat tools, anyone who prefers speaking to typing.

## Core user flow (golden path)

1. App launches, sits in the system tray (no visible window required).
2. User holds F9 (or their configured hotkey) anywhere on the system.
3. A floating status pill appears showing "Recording."
4. User releases the key.
5. Pill switches to "Transcribing," then disappears.
6. The cleaned-up transcribed text is typed directly into whatever window had focus at release time.

## Requirements

### Must have (shipped)

- Hold-to-talk global hotkey, user-configurable among a curated set of F-keys/rare keys (never a normal typing key — would break typing systemwide).
- Local, offline speech-to-text (faster-whisper) — no per-use cost, no audio leaves the device for transcription.
- Works correctly across different microphones (Bluetooth headset, laptop internal mic) without hardcoded sample-rate assumptions.
- Rule-based filler-word/formatting cleanup (no LLM call — zero incremental cost).
- Runs quietly from the tray; closing the window doesn't quit the app.
- Single-instance enforcement (two copies running at once double-types every keystroke).
- Dictation history, usage stats (words, WPM, streak).
- Settings: microphone picker, dictation language, custom vocabulary, filler-cleanup toggle, push-to-talk vs. toggle mode, per-app exclusion list, Whisper model size picker, sound cues, one-click update download.
- Auto-update check (notify-only — never silent install) against GitHub Releases.
- Local crash logging, no telemetry.
- Standalone Windows installer, no admin rights required, MIT-licensed and open source.
- Android companion: a custom keyboard (IME) covering the "can't get a real global hotkey" constraint on Android, plus a floating-bubble overlay mode as a second interaction style. Bundled on-device Whisper (via sherpa-onnx) with an online-fallback recognizer.

### Should have (partially built, gated behind Pro / not yet sellable)

- **VoxScribe Pro tier**: offline Ed25519-signed license keys (no account, no network call to verify), unlocking:
  - **Snippets** — say a trigger phrase, get an expanded string typed instead.
- A real storefront / purchase flow (planned: Gumroad first, due to zero-setup global tax handling; Stripe only if Gumroad's cut becomes material at volume).
- Key delivery automation (planned: Gumroad webhook → Vercel Function → keygen; currently manual).

### Could have (discussed, not built)

- Larger Whisper models (`medium`/`large`) as Pro-only tiers.
- Snippet template variables (`{date}`, `{time}`, `{clipboard}`).
- Cross-device sync (would require Supabase + device pairing + client-side encryption — deliberately deferred until Pro has paying users to justify the build).
- Code signing (removes the Windows SmartScreen warning) — scripted and ready, blocked only on the user purchasing a certificate.
- A raised UI ceiling beyond PySide6/QSS (QML recommended, not yet decided/actioned — see [ARCHITECTURE.md](ARCHITECTURE.md#open-decision-uiframework-ceiling)).

### Explicitly out of scope

- Any cloud LLM call for tone/style rewriting or a "Notetaker"-style feature — would compromise the local-only privacy differentiator that is the whole point of the product versus Wispr Flow.
- Silent/automatic app updates — judged too risky at this project's scale (overwriting a running `.exe` + elevation handling).
- Telemetry/analytics beyond purely local, on-device counters.
- Clipboard-based text delivery on desktop (would clobber the user's clipboard) — the one deliberate exception is Android accessibility insertion into fields that don't support direct text-setting (e.g. some WebViews), where clipboard+paste is used and the previous clipboard contents are restored immediately after.

## Success signals

- No informal target metrics defined yet — this is a pre-revenue, pre-storefront hobby-to-small-business project. The practical bar so far has been "the developer/user actually dictates with it daily and it doesn't crash or double-type."
- Once a storefront exists: first paying Pro customer, then whether manual key delivery becomes annoying enough to justify webhook automation.

## Key product decisions and their rationale

- **Hold-to-talk, not auto-VAD.** Silero VAD auto-detection was tried and dropped — the user's Bluetooth headset produced classifier probabilities too low/inconsistent to trust as a start/stop trigger, causing false triggers and Whisper hallucination on noise. Explicit hold-to-talk proved more reliable. See [ARCHITECTURE.md](ARCHITECTURE.md#voice-activity-detection-not-used-live).
- **Local rule-based cleanup, not an LLM call.** Keeps the product's cost structure at $0 per use and keeps the "fully local" privacy claim honest.
- **Android is a keyboard app, not a global-hotkey app.** Android deliberately blocks apps from grabbing global hotkeys that inject text into an arbitrary focused app (a real privacy/security boundary in the OS) — the closest equivalent is a custom IME plus, as a second mode, an accessibility-service-driven floating bubble (the same approach Wispr Flow itself uses on Android).
- **Freemium via a local license key, not an account/subscription.** Chosen deliberately to start lean — a real Pro feature (Snippets) gated by offline signature verification, rather than building a sync backend before there's a single paying customer.
