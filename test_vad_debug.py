"""Prints raw VAD speech-probability per frame for a few seconds, for debugging threshold issues."""
import time

from core.audio_capture import frames, _default_input_device
from core.vad import SileroVAD
import sounddevice as sd

_dev = _default_input_device()
print(f"Using device {_dev}: {sd.query_devices(_dev)['name'] if _dev is not None else None}")

vad = SileroVAD(gain=1.0)
print("Loading done.")
for i in range(3, 0, -1):
    print(f"Speak in {i}...", flush=True)
    time.sleep(1)
print("SPEAK NOW\n", flush=True)

count = 0
for frame in frames():
    prob = vad.speech_probability(frame)
    print(f"prob={prob:.4f}")
    count += 1
    if count >= 150:  # ~150 frames * 32ms ~= 4.8s
        break
