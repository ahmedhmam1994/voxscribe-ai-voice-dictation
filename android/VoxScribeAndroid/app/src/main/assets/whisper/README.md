Download `sherpa-onnx-whisper-tiny.en.tar.bz2` from
https://github.com/k2-fsa/sherpa-onnx/releases/tag/asr-models, extract it,
and place these three files directly in this folder:

- `tiny.en-encoder.int8.onnx`
- `tiny.en-decoder.int8.onnx`
- `tiny.en-tokens.txt`

See `README-ANDROID.md` → "Milestone 2: getting the pieces" in the project
root for details. Not committed to git (see `.gitignore`) because they're
large binaries nobody can meaningfully diff. Without them, `WhisperEngine`
detects they're missing and the app automatically falls back to Milestone
1's `SpeechRecognizer` path instead — no crash, no build break.
