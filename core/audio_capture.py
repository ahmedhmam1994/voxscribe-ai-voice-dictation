"""Microphone audio capture.

Streams mic input via `sounddevice` and yields fixed-size int16 mono frames
at 16kHz, sized for the Silero VAD ONNX model (512-sample frames = 32ms).
"""

from __future__ import annotations

import queue
from collections.abc import Generator

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16_000
# Silero VAD (ONNX) expects exactly 512 samples per frame at 16kHz.
FRAME_SIZE = 512


def _default_input_device() -> int | None:
    """Pick a sensible default input device.

    sounddevice's overall default can land on an MME entry that only
    natively supports 44100Hz; for some devices (notably Bluetooth
    headsets over HFP) requesting 16kHz through that driver yields
    near-silent audio. Prefer the WASAPI entry for the same physical
    device when one exists, since it exposes the device's true native
    sample rate.
    """
    try:
        wasapi_idx = next(
            i for i, api in enumerate(sd.query_hostapis()) if api["name"] == "Windows WASAPI"
        )
    except StopIteration:
        return None
    wasapi_default = sd.query_hostapis()[wasapi_idx]["default_input_device"]
    return wasapi_default if wasapi_default != -1 else None


def resample_to_16k(audio: np.ndarray, source_rate: int) -> np.ndarray:
    """Linearly resample a 1-D float32 buffer from `source_rate` to 16kHz.

    Devices vary in their native sample rate (e.g. a laptop's internal mic
    is often 48000Hz, while some Bluetooth headsets expose 16000Hz
    natively), and forcing a stream to open at a rate the device doesn't
    support raises `PortAudioError: Invalid sample rate` on some drivers.
    Recording at the device's own native rate and resampling here in
    software sidesteps that, regardless of which mic ends up being the
    default.
    """
    if source_rate == SAMPLE_RATE or len(audio) == 0:
        return audio.astype(np.float32)
    duration = len(audio) / source_rate
    target_len = max(1, round(duration * SAMPLE_RATE))
    src_x = np.linspace(0, 1, num=len(audio), endpoint=False)
    dst_x = np.linspace(0, 1, num=target_len, endpoint=False)
    return np.interp(dst_x, src_x, audio).astype(np.float32)


def device_native_samplerate(device: int | None) -> int:
    """Return the given device's native sample rate (falls back to 16000)."""
    if device is None:
        return SAMPLE_RATE
    try:
        return int(round(sd.query_devices(device)["default_samplerate"]))
    except Exception:  # noqa: BLE001
        return SAMPLE_RATE


def frames(
    sample_rate: int = SAMPLE_RATE,
    frame_size: int = FRAME_SIZE,
    device: int | str | None = None,
) -> Generator[np.ndarray, None, None]:
    """Open the default (or given) microphone and yield audio frames forever.

    Each yielded frame is a 1-D float32 numpy array of length `frame_size`,
    containing mono audio in the [-1.0, 1.0] range at `sample_rate` Hz —
    the format Silero VAD expects.

    This is a generator, so it must be driven by a `for` loop (or manually
    via `next()`); closing/breaking out of the loop stops the stream
    cleanly (see the `finally` block).

    Raises whatever `sounddevice` raises if no input device is available.
    """
    if device is None:
        device = _default_input_device()

    audio_q: "queue.Queue[np.ndarray]" = queue.Queue()

    def _callback(indata, frame_count, time_info, status):  # noqa: ANN001
        if status:
            # Overflow/underflow etc. — non-fatal, just surface it.
            print(f"[audio_capture] stream status: {status}")
        # indata is shape (frame_count, channels); we asked for 1 channel.
        audio_q.put(indata[:, 0].copy())

    stream = sd.InputStream(
        samplerate=sample_rate,
        blocksize=frame_size,
        channels=1,
        dtype="float32",
        device=device,
        callback=_callback,
    )
    with stream:
        while True:
            yield audio_q.get()
