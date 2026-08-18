# VoxScribe for Android — starter project

This is a starting point for an Android version of VoxScribe (your Windows
voice-dictation app). It's a real, working design — not just a mockup — but
you'll need Android Studio on your own machine to build and run it, since
that's not something this cloud session can do for you.

## Why it's built as a keyboard, not a "hold F9 anywhere" app

The desktop app works by grabbing a **global hotkey** and typing directly
into whatever window has focus. Android deliberately doesn't allow apps to
do that (it would be a huge privacy/security hole — any app could then type
into your banking app). The closest legitimate equivalent Android provides
is a **custom keyboard (an "Input Method Editor" / IME)**: once you switch to
it in any app, it *is* the thing with access to the focused text field, so a
mic button on it can insert text directly — same practical result as the
desktop app, using the mechanism Android actually gives you for it.

So: VoxScribe-Android shows up in your keyboard picker like Gboard does.
Switch to it, hold the mic button, talk, release — the transcribed (and
cleaned-up) text gets typed into whatever field you're in.

## What's included

```
app/src/main/kotlin/com/voxscribe/android/
  VoxScribeInputMethodService.kt   The keyboard itself: hold-to-talk mic button,
                                    picks Whisper or the fallback recognizer,
                                    inserts text.
  WhisperEngine.kt                 Milestone 2: bundled on-device Whisper via
                                    sherpa-onnx. Falls back gracefully (see
                                    below) if its model files aren't present.
  TranscriptCleanup.kt             Direct Kotlin port of your desktop
                                    core/cleanup.py filler-word/spacing cleanup.
  SetupActivity.kt                 The only "real" screen -- walks you through
                                    the one-time Android setup steps.
  PermissionActivity.kt            Tiny invisible helper: a Service (the IME)
                                    can't pop a permission dialog itself, so it
                                    launches this to ask for microphone access.
app/src/main/res/
  layout/keyboard_view.xml         The keyboard's UI (mic button + basic keys).
  xml/method.xml                   Registers this as an Android input method.
  values/strings.xml               All user-facing text.
  drawable/ic_launcher.xml          Placeholder icon -- swap via Android Studio's
                                    Image Asset tool whenever you like.
app/src/main/AndroidManifest.xml   Declares the keyboard service + permissions.
app/build.gradle.kts               Module build config (references the AAR
                                    you'll add per Milestone 2 below).
app/libs/                          Where the sherpa-onnx AAR goes (gitignored --
                                    you download it, not committed to the repo).
app/src/main/assets/whisper/       Where the Whisper model files go (gitignored --
                                    same reason).
.gitignore                         Excludes standard Gradle/Android build output
                                    plus the two binary dependencies above.
```

## Milestone 1: on-device, using Android's built-in recognizer

`VoxScribeInputMethodService` can fall back to Android's built-in
`SpeechRecognizer` with `EXTRA_PREFER_OFFLINE = true`. On most phones this
runs fully on-device once the "offline speech recognition" language pack is
downloaded (**Settings > System > Languages & input > On-screen keyboard >
Google voice typing > Offline speech recognition** — exact path varies by
phone/Android version).

This is a real, working path with zero native-code build steps, and it's
still what the app uses automatically whenever Milestone 2's bundled model
isn't present — see "Automatic fallback" below.

**Tradeoff to know about:** it depends on the device having that language
pack installed and on Google's voice-typing components being present at all
(most phones with Google Play services have this; some don't). It's not
literally "bundled in the app" the way faster-whisper is bundled with the
desktop build — Milestone 2 closes that gap.

## Milestone 2: bundled Whisper via sherpa-onnx (now implemented)

`WhisperEngine.kt` and the recording path in
`VoxScribeInputMethodService.kt` now use
**[sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)**'s offline
recognizer with a bundled, quantized Whisper `tiny.en` model — the same
practical shape as the desktop app's faster-whisper: local model, no
per-request network call, no dependency on the phone's own voice-typing
settings.

**IMPORTANT — not build-verified.** This was written by cross-referencing
sherpa-onnx's actual published Kotlin API source and its official Android
demo apps on GitHub (not guessed API calls), but there is no Android SDK or
emulator available in the environment this was written in, so it has never
actually been compiled or run. Budget time for the first build to surface
something small (an import, a Gradle wiring detail, an ABI issue) — this is
a strong starting point, not a proven one.

### Getting the pieces (two binary downloads this repo doesn't ship)

Both are gitignored on purpose — they're large binaries nobody can
meaningfully diff in git, so they're a one-time manual step instead:

1. **The sherpa-onnx AAR.** Download `sherpa-onnx-1.13.6.aar` from
   [the sherpa-onnx v1.13.6 release](https://github.com/k2-fsa/sherpa-onnx/releases/tag/v1.13.6)
   and place it at `app/libs/sherpa-onnx-1.13.6.aar`. (If a newer version has
   since been released, either grab that version's `.aar` and update the
   filename in `app/build.gradle.kts` to match, or find `v1.13.6` under
   "previous releases" — the API this project uses is version-stable within
   the 1.13.x line as of this writing.)

2. **The Whisper `tiny.en` model**, from the same repo's
   [`asr-models` release](https://github.com/k2-fsa/sherpa-onnx/releases/tag/asr-models):
   download `sherpa-onnx-whisper-tiny.en.tar.bz2`, extract it, and copy
   three files into `app/src/main/assets/whisper/`:
   - `tiny.en-encoder.int8.onnx` (~12MB)
   - `tiny.en-decoder.int8.onnx` (~105MB)
   - `tiny.en-tokens.txt`

   (`~117MB` added to the app via bundled assets — small next to the
   desktop app's own model download, and it means the APK is fully
   self-contained with no first-run download step, unlike the desktop app.
   A first-run downloader instead of bundling is a reasonable future
   simplification if the APK size becomes a concern, but bundling is the
   simpler and more reliable starting point given this can't be test-built
   here.)

### Automatic fallback

`WhisperEngine.isAvailable()` checks whether all three model files above
are present in `assets/whisper/` before ever trying to load them. If you
skip this step (or haven't gotten to it yet), the keyboard **still works** —
it silently uses Milestone 1's `SpeechRecognizer` path instead, no crash, no
broken build. The status text at the top of the keyboard tells you which
one is active ("Ready (offline Whisper)" vs. "Ready (online recognizer)"),
so you can confirm which path actually ran.

The same fail-open behavior applies if the AAR/model load succeeds but
throws at runtime (wrong AAR version, corrupted model file, unsupported
device ABI) — `WhisperEngine` catches that and falls back rather than
leaving the IME stuck.

## Getting this running (step by step)

You'll need [Android Studio](https://developer.android.com/studio) installed
(free). This project intentionally does **not** ship a Gradle wrapper —
hand-crafting one blind risks a version mismatch that's confusing to debug
as a first Android project. Instead:

1. Open Android Studio → **New Project** → **Empty Views Activity** →
   language **Kotlin**, package name `com.voxscribe.android`, minimum SDK
   API 26. Let it finish its initial Gradle sync (this generates a correct,
   working wrapper for your installed Android Studio version).
2. Close that project. In a file explorer, copy the contents of this
   `VoxScribeAndroid/app/src/main/` folder (kotlin/, res/, AndroidManifest.xml)
   **over** the same folder in the project Android Studio just created,
   replacing its defaults.
3. Open the new project's `app/build.gradle.kts` and merge in the
   `dependencies { ... }` block from this project's `app/build.gradle.kts`
   (add the `androidx.appcompat` line and the `implementation(files("libs/..."))`
   line if the wizard didn't already include equivalents).
4. **If you want Milestone 2's bundled Whisper** (recommended — otherwise
   you'll be on the Milestone 1 fallback the whole time): follow "Getting
   the pieces" above first — download the AAR into `app/libs/` and the three
   model files into `app/src/main/assets/whisper/` — before syncing Gradle.
   Skipping this is fine too; the app still runs, just on the fallback path.
5. Sync Gradle again (Android Studio will prompt you, or **File > Sync
   Project with Gradle Files**). If you added the AAR, this is the step
   most likely to surface a version/API mismatch — see the "not
   build-verified" note above.
6. Plug in your phone (with USB debugging enabled — Settings > About phone >
   tap "Build number" 7 times to unlock Developer options, then enable USB
   debugging) or start an emulator, and hit **Run**.
7. On first launch you'll land on the setup screen: grant the microphone
   permission, enable "VoxScribe" in the system keyboard list, then switch to
   it from any text field's keyboard-switcher icon.
8. Tap into any text field (Messages, Notes, a browser search box), switch
   keyboards to VoxScribe, hold the mic button, talk, release — the cleaned
   transcript should appear. Check the status text: "Ready (offline Whisper)"
   confirms Milestone 2 loaded; "Ready (online recognizer)" means it's on
   the Milestone 1 fallback.

## Known rough edges to expect on a first run

- If Milestone 2's AAR/model setup has any mismatch, `WhisperEngine` is
  designed to fail closed to the Milestone 1 fallback rather than crash —
  but since this hasn't been build-tested, treat "it silently stayed on the
  fallback path" as a real possibility to debug, not just a hypothetical.
- On the Milestone 1 fallback: if your phone doesn't have the offline
  language pack, `SpeechRecognizer` may return an error or silently use an
  online fallback — check `status_error` on screen and see the Milestone 1
  tradeoff note above.
- Some OEM Android skins (Samsung, Xiaomi, etc.) restrict third-party
  keyboards more aggressively — you may need to explicitly allow "full
  access" for the keyboard in system settings the first time.
- There's no audio visualizer / VAD yet (the desktop app's floating
  indicator has no analog here yet) — recording runs until you release the
  mic button, with no separate end-of-speech trim on the Whisper path.

## If you'd like help with the next step

Once you've got this running on your phone and can confirm the flow works
(on either path), come back and I can help with whichever is most useful:
debugging a first-build issue in the Whisper path, a nicer keyboard UI,
publishing to the Play Store, or anything that breaks along the way.
