package com.voxscribe.android

/**
 * What a touch on the floating button means, which depends on the chosen [Mode].
 *
 * BOTH (the default): holding records for as long as the finger stays down, and a
 * quick tap starts a recording that keeps going until the next tap, so a long
 * dictation does not need a finger held on the screen.
 * HOLD: records only while the finger is down, never latches.
 * TAP: a press starts a recording and the next press stops it, however long the
 * first press lasted, so there is no timing to get wrong.
 */
class HoldOrTap(private val tapMaxMs: Long = TAP_MAX_MS) {

    enum class Action { NONE, START, STOP, CANCEL }

    enum class Mode(val key: String) {
        BOTH("both"),
        HOLD("hold"),
        TAP("tap"),
        ;

        companion object {
            /** The saved name back to a mode; anything unknown is the default. */
            fun fromKey(key: String?): Mode = values().firstOrNull { it.key == key } ?: BOTH
        }
    }

    /** Takes effect from the next touch. */
    var mode: Mode = Mode.BOTH

    private var holding = false
    private var latched = false
    private var consumed = false // this touch only stopped a running recording
    private var downAt = 0L

    /** True while a tap-started recording is running. */
    val isLatched: Boolean get() = latched

    fun down(nowMs: Long): Action {
        downAt = nowMs
        if (latched) {
            latched = false
            consumed = true
            return Action.STOP
        }
        consumed = false
        holding = true
        return Action.START
    }

    /** The touch turned into a drag, so it was never a press. */
    fun dragged(): Action {
        if (consumed || !holding) return Action.NONE
        holding = false
        return Action.CANCEL
    }

    fun up(nowMs: Long): Action {
        if (consumed) {
            consumed = false
            return Action.NONE
        }
        if (!holding) return Action.NONE
        holding = false
        val latch = when (mode) {
            Mode.HOLD -> false
            Mode.TAP -> true
            Mode.BOTH -> nowMs - downAt < tapMaxMs
        }
        if (latch) {
            latched = true
            return Action.NONE
        }
        return Action.STOP
    }

    /** Ends a tap-started recording from outside, for the safety timeout. */
    fun forceStop(): Action {
        if (!latched) return Action.NONE
        latched = false
        return Action.STOP
    }

    /** Back to idle without any action, after a failure or a restart. */
    fun reset() {
        holding = false
        latched = false
        consumed = false
    }

    companion object {
        const val TAP_MAX_MS = 300L
    }
}
