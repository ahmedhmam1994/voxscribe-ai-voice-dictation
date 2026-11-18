"""Microphone audio capture.

Streams mic input via `sounddevice` and yields fixed-size int16 mono frames
at 16kHz, sized for the Silero VAD ONNX model (512-sample frames = 32ms).
"""

from __future__ import annotations

import math
import queue
import threading
import time
from collections.abc import Generator

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16_000
# Silero VAD (ONNX) expects exactly 512 samples per frame at 16kHz.
FRAME_SIZE = 512


class RollingBuffer:
    """Keeps only the most recent `max_samples` of audio, in memory.

    Backs the optional "keep microphone ready" mode: the mic stream stays
    open and feeds this buffer, so when the hotkey is pressed the last
    fraction of a second is already captured and the first word isn't
    clipped by stream start-up lag. Nothing here is saved or transcribed
    unless a recording is actually started.
    """

    def __init__(self, max_samples: int) -> None:
        self._max = max(1, max_samples)
        self._chunks: list[np.ndarray] = []
        self._total = 0
        # push() runs on the audio callback thread, drain() on the Qt thread.
        self._lock = threading.Lock()

    def push(self, chunk: np.ndarray) -> None:
        with self._lock:
            self._chunks.append(chunk)
            self._total += len(chunk)
            while self._chunks and self._total - len(self._chunks[0]) >= self._max:
                self._total -= len(self._chunks.pop(0))

    def drain(self) -> list[np.ndarray]:
        with self._lock:
            chunks = self._chunks
            self._chunks = []
            self._total = 0
        return chunks


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
    wasapi = sd.query_hostapis()[wasapi_idx]
    wasapi_default = wasapi["default_input_device"]
    if wasapi_default == -1:
        return None
    # Enabling Stereo Mix makes Windows route its default recording device to
    # it, which records the PC's playback (silence) instead of the microphone.
    # Dictation is never meant to listen to system audio by default, so skip it.
    if is_system_audio_device(sd.query_devices(wasapi_default)["name"]):
        for idx in wasapi["devices"]:
            info = sd.query_devices(idx)
            if info["max_input_channels"] > 0 and not is_system_audio_device(info["name"]):
                return idx
    return wasapi_default


_SYSTEM_AUDIO_NAMES = ("stereo mix", "what u hear", "wave out mix", "loopback")


def is_system_audio_device(name: str) -> bool:
    """True for inputs that capture the PC's playback, not a microphone."""
    lowered = name.lower()
    return any(marker in lowered for marker in _SYSTEM_AUDIO_NAMES)


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
        label = f"{info['name']} ({hostapi_name})"
        if is_system_audio_device(info["name"]):
            label += " (system audio)"
        devices.append((idx, label))
    return devices


def device_label(index: int | None) -> str | None:
    """A device's name with its host API, "Headset (soundcore) (Windows WASAPI)".
    Saved with the user's choice, because device numbers shift whenever a
    device is connected or removed, and a saved number can end up pointing at
    a different device (a headset's number turned into Stereo Mix's)."""
    if index is None:
        return None
    try:
        info = sd.query_devices(index)
        return f"{info['name']} ({sd.query_hostapis(info['hostapi'])['name']})"
    except Exception:  # noqa: BLE001
        return None


def find_input_device(label: str) -> int | None:
    """The current number of the input device saved as `label`, or None when
    it is not connected now."""
    try:
        hostapis = sd.query_hostapis()
        for idx, info in enumerate(sd.query_devices()):
            if info["max_input_channels"] <= 0:
                continue
            if f"{info['name']} ({hostapis[info['hostapi']]['name']})" == label:
                return idx
    except Exception:  # noqa: BLE001
        pass
    return None


def resolve_input_device(preferred: int | None, label: str | None = None) -> int | None:
    """The device to actually record with: the user's chosen device if it's
    still present and can be opened, otherwise auto-detection. Handles a
    chosen device (e.g. a Bluetooth headset) being disconnected since it was
    chosen, and a saved number that now points at another device, rather than
    raising or silently recording from nothing."""
    if label:
        preferred = find_input_device(label)
    elif preferred is not None:
        # Saved before the name was kept: the number may have moved onto
        # another device. A microphone choice never means system audio.
        try:
            if is_system_audio_device(sd.query_devices(preferred)["name"]):
                preferred = None
        except Exception:  # noqa: BLE001
            preferred = None
    if preferred is not None:
        try:
            info = sd.query_devices(preferred)
            if info["max_input_channels"] > 0:
                sd.check_input_settings(
                    device=preferred,
                    channels=1,
                    dtype="float32",
                    samplerate=int(info["default_samplerate"]),
                )
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


# Some drivers deliver more samples per second than the rate they report: a
# laptop's built-in Conexant mic sent about 88,000 a second at a reported
# 44,100 (and 96,000 at 48,000), on every host API. Trusting the reported
# rate then plays the voice back at half speed, an octave low, and Whisper
# writes words that were never said. So each recording also counts what
# really arrives and resamples from that.
# A wrong rate has so far been a whole multiple of the reported one.
_RATE_RATIOS = (1 / 4, 1 / 3, 1 / 2, 1.0, 2.0, 3.0, 4.0)
_RATE_TOLERANCE = 0.25  # clock drift and burst delivery stay well inside this
_MEASURE_SEC = 0.4
_true_rates: dict[str, int] = {}


def true_rate(reported: int, measured: float) -> int:
    """`reported`, unless `measured` is clearly off; then `reported` times the
    whole ratio nearest to what really arrived."""
    if reported <= 0 or measured <= 0 or abs(measured - reported) <= _RATE_TOLERANCE * reported:
        return reported
    ratio = min(_RATE_RATIOS, key=lambda r: abs(math.log(measured / reported / r)))
    return round(reported * ratio)


class RateMeter:
    """Counts the samples a stream delivers against the clock. add() is
    called from the audio callback; rate() gives the rate to resample from."""

    def __init__(self, reported: int, device: int | None = None) -> None:
        self.reported = reported
        self._key = device_label(device) if device is not None else None
        self._first: float | None = None
        self._last: float | None = None
        self._frames = 0

    def add(self, frames: int, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        if self._first is None:
            # The clock starts at the first block, so its own samples (which
            # arrived before it) are not counted.
            self._first = now
            return
        self._frames += frames
        self._last = now

    @property
    def measured(self) -> bool:
        if self._first is None or self._last is None:
            return False
        return self._last - self._first >= _MEASURE_SEC

    def rate(self) -> int:
        """The real rate once measured, else what was seen on this device
        before, else the reported rate."""
        if self.measured:
            rate = true_rate(self.reported, self._frames / (self._last - self._first))
            if self._key:
                _true_rates[self._key] = rate
            return rate
        if self._key and self._key in _true_rates:
            return _true_rates[self._key]
        return self.reported


def chunk_level(chunk: np.ndarray, floor_db: float = -55.0, ceil_db: float = -15.0) -> float:
    """Loudness of one small audio chunk as 0.0-1.0, for the live mic meter
    in the floating pill.

    Mapped on a decibel scale (RMS between `floor_db` and `ceil_db`) rather
    than raw amplitude: the quiet Bluetooth headsets this app was built on
    peak around 0.02, which a linear meter would show as nothing at all,
    while normal speech on a laptop mic still lands near the top.
    """
    if len(chunk) == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(np.square(chunk, dtype=np.float64))))
    if rms <= 0.0:
        return 0.0
    db = 20.0 * np.log10(rms)
    return float(min(1.0, max(0.0, (db - floor_db) / (ceil_db - floor_db))))


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
    containing mono audio in the [-1.0, 1.0] range at `sample_rate` Hz,
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
            # Overflow/underflow etc., non-fatal, just surface it.
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
