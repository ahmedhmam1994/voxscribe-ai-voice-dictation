# VoxScribe for Android

Dictate into any app with the keyboard you already use. Hold the floating button, talk, release, and the text is typed into the focused text box. Transcription runs on the phone, so nothing is uploaded. The speech model is downloaded once in setup: IBM Granite Speech 5.0 TurboCTC (int8 ONNX, run with onnxruntime) for English, French, Spanish, German, Italian and Portuguese, or NVIDIA Nemotron 3.5 ASR Streaming 0.6B (sherpa-onnx) for Arabic and Turkish. Both are served from the `models-2` GitHub release and checked against a SHA-256 after download.

The UI is Flutter. The floating button, the accessibility service that types the text, and the speech engine are native Kotlin. VoxScribe is not a keyboard.

## Layout

- `lib/` Flutter app. `app/` holds the shell and theme (dark and light tokens in `app/theme/vox_colors.dart`), `features/` holds one folder per screen (`dictation`, `setup`), `shared/` holds small widgets.
- `android/app/src/main/kotlin/` native code. `SetupChannel` and `EngineChannel` are the bridges the Flutter screens call.
- `test/` unit and widget tests, including automatic contrast checks for both themes.
- Design brief and prototypes: `../VoxScribeAndroid/design/`.

## Build

```
flutter pub get
flutter analyze
flutter test
flutter build apk --debug
```

Three files are not in git and must be added by hand before the Android build works:

- `android/app/libs/sherpa-onnx-2.0.2.aar` and `android/app/libs/onnxruntime-android-1.28.0-vox.aar` (see `android/app/libs/README.md`)
- `android/keystore.properties` and the keystore, only for signed release builds (see `keystore.properties.example`)

Distribution is a signed APK. Google Play is not planned for now.
