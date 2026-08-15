"""Voice activity detection using the Silero VAD ONNX model.

Dependency note (Phase 1 decision):
The `silero-vad` PyPI package declares `torch` and `torchaudio` as
unconditional dependencies (only `onnxruntime` is an optional extra), so
installing it would pull in full PyTorch just for VAD. Since we only need
inference, not training, we skip the `silero-vad` package and instead run
the Silero VAD ONNX model directly through `onnxruntime` (already
installed).

Model source:
    https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx
Downloaded to `core/models/silero_vad.onnx` (git-ignored — re-download with
`scripts/download_vad_model.py` or the curl command in the README/commit
message if the file is missing).

The model is stateful (recurrent): each call takes the previous hidden
state and returns an updated one, so frames must be fed in order from a
single `SileroVAD` instance per audio stream.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import onnxruntime as ort

MODEL_PATH = Path(__file__).parent / "models" / "silero_vad.onnx"
SAMPLE_RATE = 16_000
FRAME_SIZE = 512  # samples per frame required by the model at 16kHz
# This user's Bluetooth headset mic (soundcore R50i NC over HFP) delivers a
# very quiet signal with no OS-level boost option available. Pushing digital
# gain much past ~15x starts clipping/distorting the waveform without
# meaningfully raising the model's speech probability further (diminishing
# returns observed: 12x -> ~0.14 peak, 25x -> ~0.18 peak, not proportional).
# Instead of over-amplifying, lower the threshold: background noise on this
# mic sits around 0.0005-0.001, so even a peak of ~0.15 is ~150-300x the
# noise floor -- comfortably safe from false positives.
# A fixed gain over- or under-amplifies depending on how loud a given moment
# of speech happens to be (this user's voice varies enough through a
# sentence that a fixed multiplier only reliably crossed the threshold on
# the loudest word). Instead, auto-adjust gain per-frame based on a
# short-term running estimate of the signal level, so quiet and loud
# moments both land near the same target level before the VAD sees them.
# Even with auto-gain pushing the signal toward AGC_TARGET_LEVEL, this
# user's Bluetooth headset (compressed/narrowband HFP audio) caps the
# model's confidence around ~0.1-0.2 for real speech -- this looks like an
# audio-quality ceiling, not a loudness problem, since further gain stopped
# helping. Background noise on this mic sits at ~0.0005-0.001, so a
# threshold of 0.06 is still a ~60-100x margin above the noise floor.
DEFAULT_THRESHOLD = 0.1
AGC_TARGET_LEVEL = 0.15  # target average |amplitude| after auto-gain
AGC_SMOOTHING = 0.9  # closer to 1.0 = slower-adapting level estimate
AGC_MAX_GAIN = 80.0


class SileroVAD:
    """Stateful wrapper around the Silero VAD ONNX model.

    Feed it consecutive audio frames (512 samples / 32ms at 16kHz) via
    `is_speech()`. Internal recurrent state carries over between calls, so
    create one instance per audio stream and call it in order — don't share
    an instance across unrelated streams without calling `reset()` first.
    """

    def __init__(
        self,
        model_path: Path | str = MODEL_PATH,
        threshold: float = DEFAULT_THRESHOLD,
        use_agc: bool = True,
    ):
        if not Path(model_path).exists():
            raise FileNotFoundError(
                f"Silero VAD model not found at {model_path}. "
                "Download it from https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"
            )
        self.threshold = threshold
        # Auto gain control: some input devices (e.g. Bluetooth headset mics
        # over HFP) deliver a much quieter signal than a normal mic, and the
        # loudness can vary a lot within a single sentence. Rather than a
        # fixed multiplier (which under-amplifies quiet moments or clips
        # loud ones), track a running level estimate and scale each frame
        # toward a target level before inference.
        self.use_agc = use_agc
        self._agc_level = AGC_TARGET_LEVEL
        self._session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._sr = np.array(SAMPLE_RATE, dtype=np.int64)

    def reset(self) -> None:
        """Clear recurrent state (call when starting a new/unrelated stream)."""
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._agc_level = AGC_TARGET_LEVEL

    def speech_probability(self, frame: np.ndarray) -> float:
        """Run one frame through the model, return the speech probability (0-1).

        `frame` must be a 1-D float32 array of exactly FRAME_SIZE samples.
        """
        if frame.shape != (FRAME_SIZE,):
            raise ValueError(f"expected a frame of shape ({FRAME_SIZE},), got {frame.shape}")

        x = frame.reshape(1, -1).astype(np.float32)
        if self.use_agc:
            frame_level = float(np.mean(np.abs(frame)))
            self._agc_level = AGC_SMOOTHING * self._agc_level + (1 - AGC_SMOOTHING) * frame_level
            gain = min(AGC_TARGET_LEVEL / max(self._agc_level, 1e-6), AGC_MAX_GAIN)
            x = np.clip(x * gain, -1.0, 1.0)
        out, self._state = self._session.run(
            None,
            {"input": x, "state": self._state, "sr": self._sr},
        )
        return float(out[0][0])

    def is_speech(self, frame: np.ndarray) -> bool:
        """Return True if `frame` is classified as speech (prob >= threshold)."""
        return self.speech_probability(frame) >= self.threshold
