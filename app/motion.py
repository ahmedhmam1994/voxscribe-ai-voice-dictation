"""Small shared animation helpers for the window and the floating pill.

Every helper checks Windows' "Show animations in Windows" setting first and
jumps straight to the end state when it's off, so motion never hides
information from someone who turned it off.
"""

from __future__ import annotations

import ctypes

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QVariantAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel, QProgressBar, QWidget


def animations_enabled() -> bool:
    """Windows' "Show animations in Windows" setting (SPI_GETCLIENTAREAANIMATION).
    Defaults to on if it can't be read."""
    try:
        value = ctypes.c_int(1)
        ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(value), 0)
        return bool(value.value)
    except Exception:  # noqa: BLE001
        return True


def animate_progress(bar: QProgressBar, value: int, duration_ms: int = 450) -> None:
    """Glides a progress bar to `value` instead of jumping, so a slow download
    or a long file reads as moving rather than stuck."""
    old = getattr(bar, "_vox_anim", None)
    if old is not None:
        old.stop()
    if not animations_enabled() or value <= bar.value():
        # Going backwards (a new batch) should be instant, not a slide down.
        bar.setValue(value)
        return
    anim = QPropertyAnimation(bar, b"value", bar)
    anim.setDuration(duration_ms)
    anim.setStartValue(bar.value())
    anim.setEndValue(value)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    bar._vox_anim = anim  # keep a reference while it runs
    anim.start()


def count_up(
    label: QLabel, start: int, end: int, fmt: str = "{:,}", duration_ms: int = 700
) -> None:
    """Counts a number label from `start` to `end`."""
    old = getattr(label, "_vox_anim", None)
    if old is not None:
        old.stop()
    if not animations_enabled() or start == end:
        label.setText(fmt.format(end))
        return
    anim = QVariantAnimation(label)
    anim.setDuration(duration_ms)
    anim.setStartValue(float(start))
    anim.setEndValue(float(end))
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.valueChanged.connect(lambda v: label.setText(fmt.format(int(round(v)))))
    anim.finished.connect(lambda: label.setText(fmt.format(end)))
    label._vox_anim = anim
    anim.start()


def fade_in(widget: QWidget, duration_ms: int = 320) -> None:
    """Fades a newly added widget in. The opacity effect is removed again at
    the end, since a lingering one costs repaints and blurs text slightly."""
    if not animations_enabled():
        return
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration_ms)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.finished.connect(lambda: widget.setGraphicsEffect(None))
    widget._vox_anim = anim
    anim.start()
