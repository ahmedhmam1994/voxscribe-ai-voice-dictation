"""Manual live-mic test for Phase 2 (audio capture + VAD).

Talk into your microphone; watch the console for speech/silence transitions.
Press Ctrl+C to stop.

Run with:
    venv\\Scripts\\python.exe test_vad.py
"""

from __future__ import annotations

from core.audio_capture import frames
from core.vad import SileroVAD

# Require a few consecutive frames on each side of a transition before
# printing, so a single noisy frame doesn't cause flicker in the output.
# Each frame is ~32ms, so 3 frames ~= 96ms.
CONSECUTIVE_FRAMES_TO_SWITCH = 3


def main() -> None:
    print("Loading Silero VAD model...")
    vad = SileroVAD()
    print("Opening microphone (16kHz mono)... speak to test. Ctrl+C to stop.\n")

    speaking = False
    run_length = 0

    try:
        for frame in frames():
            is_speech = vad.is_speech(frame)

            if is_speech == speaking:
                run_length = 0
                continue

            run_length += 1
            if run_length < CONSECUTIVE_FRAMES_TO_SWITCH:
                continue

            speaking = is_speech
            run_length = 0
            if speaking:
                print("Speech detected")
            else:
                print("Silence")
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
