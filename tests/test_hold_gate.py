"""Tests for core/hold_gate.py: the hold-delay gate that makes Shift safe as a hotkey."""

from core.hold_gate import HoldGate


class FakeTimer:
    """Stands in for threading.Timer: records the callback, fires on demand."""

    instances: list["FakeTimer"] = []

    def __init__(self, delay, callback):
        self.delay = delay
        self.callback = callback
        self.cancelled = False
        self.daemon = False
        FakeTimer.instances.append(self)

    def start(self):
        pass

    def cancel(self):
        self.cancelled = True

    def fire(self):
        if not self.cancelled:
            self.callback()


def make_gate():
    FakeTimer.instances = []
    events = []
    gate = HoldGate(
        on_activate=lambda: events.append("on"),
        on_deactivate=lambda: events.append("off"),
        delay=0.35,
        timer_factory=FakeTimer,
    )
    return gate, events


def test_holding_alone_activates_then_release_deactivates():
    gate, events = make_gate()
    gate.key_down()
    FakeTimer.instances[-1].fire()
    assert events == ["on"]
    gate.key_up()
    assert events == ["on", "off"]


def test_quick_tap_never_activates():
    gate, events = make_gate()
    gate.key_down()
    gate.key_up()
    FakeTimer.instances[-1].fire()
    assert events == []


def test_other_key_before_delay_cancels_for_this_hold():
    gate, events = make_gate()
    gate.key_down()
    gate.other_key_down()  # typing a capital letter
    FakeTimer.instances[-1].fire()
    gate.key_up()
    assert events == []


def test_other_modifier_already_held_blocks_activation():
    gate, events = make_gate()
    gate.key_down(other_modifier_held=True)  # e.g. Ctrl+Shift
    assert FakeTimer.instances == []
    gate.key_up()
    assert events == []


def test_other_key_after_activation_does_not_deactivate():
    gate, events = make_gate()
    gate.key_down()
    FakeTimer.instances[-1].fire()
    gate.other_key_down()
    assert events == ["on"]
    gate.key_up()
    assert events == ["on", "off"]


def test_key_repeat_does_not_restart_timer():
    gate, events = make_gate()
    gate.key_down()
    gate.key_down()
    gate.key_down()
    assert len(FakeTimer.instances) == 1


def test_gate_resets_after_release_so_next_hold_works():
    gate, events = make_gate()
    gate.key_down()
    gate.other_key_down()
    gate.key_up()
    gate.key_down()
    FakeTimer.instances[-1].fire()
    assert events == ["on"]
