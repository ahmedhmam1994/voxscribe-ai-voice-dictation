Download `sherpa-onnx-whisper-base.tar.bz2` (the **multilingual base**
variant) from
https://github.com/k2-fsa/sherpa-onnx/releases/tag/asr-models, extract it,
and place these three files directly in this folder:

- `base-encoder.int8.onnx`
- `base-decoder.int8.onnx`
- `base-tokens.txt`

See `README-ANDROID.md` → "Milestone 2: getting the pieces" in the project
root for the full model-size history (`tiny.en` → multilingual `tiny` →
`base`, each step driven by a real on-device testing failure, not a
preemptive choice). Not committed to git (see `.gitignore`) because they're
large binaries nobody can meaningfully diff. Without them, `WhisperEngine`
detects they're missing and the app automatically falls back to Milestone
1's `SpeechRecognizer` path instead — no crash, no build break.
