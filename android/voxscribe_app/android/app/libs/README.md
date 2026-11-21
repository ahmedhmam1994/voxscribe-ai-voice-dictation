Download `sherpa-onnx-2.0.2.aar` from
https://github.com/k2-fsa/sherpa-onnx/releases/tag/v2.0.2 and place it in
this folder (the `sherpa-onnx-2.0.2.aar` asset of that release). It runs
the Nemotron model for Arabic and Turkish. Not committed to git (see `.gitignore`)
because it's a large binary nobody can meaningfully diff.

Also build `onnxruntime-android-1.28.0-vox.aar` here, which runs the Granite
model: download `onnxruntime-android-1.28.0.aar` from Maven Central
(com.microsoft.onnxruntime:onnxruntime-android:1.28.0) and run

    python tools/make_ort_aar.py path/to/onnxruntime-android-1.28.0.aar

from the `android` folder. The script explains why: both AARs carry a
libonnxruntime.so, only one can ship, and this points onnxruntime's Java bridge
at sherpa-onnx's copy. Redo it when either library's version changes.
