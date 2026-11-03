"""Tests for core/firstrun.py: the classifiers must only ever return fixed codes."""

import core.firstrun as firstrun


def test_model_errors_map_to_fixed_codes():
    assert firstrun.classify_model_error("Connection timed out") == "network"
    assert firstrun.classify_model_error("[Errno 28] No space left on device") == "disk"
    assert firstrun.classify_model_error("Access is denied: model.bin") == "blocked"
    assert firstrun.classify_model_error("something odd") == "other"
    assert firstrun.classify_model_error("") == "other"


def test_mic_errors_map_to_fixed_codes():
    assert firstrun.classify_mic_error("Permission denied") == "denied"
    assert firstrun.classify_mic_error("No default input device available") == "no_device"
    assert firstrun.classify_mic_error("Device unavailable, in use by another app") == "busy"
    assert firstrun.classify_mic_error("PortAudioError -9999") == "other"


def test_hotkey_errors_map_to_fixed_codes():
    assert firstrun.classify_hotkey_error("Access denied, run as administrator") == "blocked"
    assert firstrun.classify_hotkey_error("hotkey already registered") == "conflict"
    assert firstrun.classify_hotkey_error("boom") == "other"


def test_seconds_bucket_edges():
    assert firstrun.seconds_bucket(0.5) == "under_2s"
    assert firstrun.seconds_bucket(2) == "2_5s"
    assert firstrun.seconds_bucket(5) == "5_15s"
    assert firstrun.seconds_bucket(15) == "over_15s"


def test_mic_kind_never_returns_the_device_name():
    assert firstrun.mic_kind("Headset (Galaxy Buds2 Hands-Free)") == "bluetooth"
    assert firstrun.mic_kind("USB Audio Device") == "usb"
    assert firstrun.mic_kind("Microphone Array (Realtek)") == "built_in"
    assert firstrun.mic_kind("Something unique 42") == "other"
    assert firstrun.mic_kind(None) == "other"


def test_classify_activation_codes():
    assert firstrun.classify_activation(True, "ok") == "activated"
    assert firstrun.classify_activation(False, "This key is already active on two PCs.") == "device_limit"
    assert firstrun.classify_activation(False, "That key isn't valid -- check for typos") == "bad_key"
    assert firstrun.classify_activation(False, "Couldn't reach the activation server: x") == "network"
    assert firstrun.classify_activation(False, "boom") == "other"


def test_feature_sends_only_known_names(monkeypatch):
    sent = []
    monkeypatch.setattr(
        firstrun.telemetry, "send_once_keyed", lambda key, event, **p: sent.append((key, event, p))
    )
    firstrun.feature("snippets")
    firstrun.feature("my secret thing")
    assert sent == [("snippets", "feature_used", {"feature": "snippets"})]
