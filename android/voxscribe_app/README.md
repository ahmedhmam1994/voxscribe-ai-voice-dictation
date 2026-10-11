# VoxScribe for Android

Dictate into any app with the keyboard you already use. Hold the floating button, talk, release, and the text is typed into the focused text box. Transcription runs on the phone with Whisper (sherpa-onnx), so nothing is uploaded.

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

- `android/app/libs/sherpa-onnx-1.13.6.aar` (see `android/app/libs/README.md`)
- `android/app/src/main/assets/whisper/` model files (see the README there)
- `android/keystore.properties` and the keystore, only for signed release builds (see `keystore.properties.example`)

Distribution is a signed APK. Google Play is not planned for now.
