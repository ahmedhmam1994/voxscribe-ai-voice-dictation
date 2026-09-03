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


def list_input_devices() -> list[tuple[int, str]]:
    """Real input-capable devices, as (device_index, display_name) pairs.

    Used to populate the microphone picker in Settings. Filters to devices
    that actually support input (max_input_channels > 0) -- sounddevice's
    device list includes output-only devices too. The host API name is
    appended to the label since the same physical device often appears
    multiple times under different APIs (MME, WASAPI, DirectSound), and
    they're not interchangeable -- see _default_input_device()'s docstring
    on why WASAPI specifically is preferred for the auto-detected default.
    """
    hostapis = sd.query_hostapis()
    devices = []
    for idx, info in enumerate(sd.query_devices()):
        if info["max_input_channels"] <= 0:
            continue
        hostapi_name = hostapis[info["hostapi"]]["name"]
        devices.append((idx, f"{info['name']} ({hostapi_name})"))
    return devices


def resolve_input_device(preferred: int | None) -> int | None:
    """The device to actually record with: the user's chosen device if it's
    still present, otherwise falls back to auto-detection -- handles a
    previously-selected device (e.g. a Bluetooth headset) being disconnected
    or unplugged since it was chosen, rather than raising or silently
    recording from nothing."""
    if preferred is not None:
        try:
            if sd.query_devices(preferred)["max_input_channels"] > 0:
                return preferred
        except Exception:  # noqa: BLE001
            pass
    return _default_input_device()


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


def peak_levels(
    device: int | None = None,
    chunk_ms: int = 50,
) -> Generator[float, None, None]:
    """Open the given (or auto-detected) microphone and yield the peak
    absolute amplitude (0.0-1.0) of each successive small chunk, forever.

    Powers the Settings "Test microphone" calibration check -- a live level
    meter needs small, frequent chunks rather than frames()'s fixed
    512-sample/16kHz VAD framing, and doesn't need resampling since nothing
    downstream consumes the raw samples, just their peak amplitude.
    """
    if device is None:
        device = _default_input_device()
    rate = device_native_samplerate(device)
    chunk_size = max(1, int(rate * chunk_ms / 1000))

    audio_q: "queue.Queue[np.ndarray]" = queue.Queue()

    def _callback(indata, frame_count, time_info, status):  # noqa: ANN001
        audio_q.put(indata[:, 0].copy())

    stream = sd.InputStream(
        samplerate=rate,
        blocksize=chunk_size,
        channels=1,
        dtype="float32",
        device=device,
        callback=_callback,
    )
    with stream:
        while True:
            chunk = audio_q.get()
            yield float(np.abs(chunk).max()) if len(chunk) else 0.0


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
