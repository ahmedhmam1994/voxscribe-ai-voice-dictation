Download `sherpa-onnx-whisper-tiny.tar.bz2` (the **multilingual** variant —
not `tiny.en`) from
https://github.com/k2-fsa/sherpa-onnx/releases/tag/asr-models, extract it,
and place these three files directly in this folder:

- `tiny-encoder.int8.onnx`
- `tiny-decoder.int8.onnx`
- `tiny-tokens.txt`

See `README-ANDROID.md` → "Milestone 2: getting the pieces" in the project
root for details. Not committed to git (see `.gitignore`) because they're
large binaries nobody can meaningfully diff. Without them, `WhisperEngine`
detects they're missing and the app automatically falls back to Milestone
1's `SpeechRecognizer` path instead — no crash, no build break.

Multilingual, not the English-only `tiny.en` variant — `WhisperEngine.kt`
sets `language = ""`, which sherpa-onnx treats as "auto-detect the spoken
language" rather than assuming English.
