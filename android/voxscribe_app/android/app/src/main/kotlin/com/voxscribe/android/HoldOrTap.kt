package com.voxscribe.android

/**
 * What a touch on the floating button means. Holding it records for as long as
 * the finger stays down, as before. A quick tap starts a recording that keeps
 * going, and the next tap stops it, so a long dictation does not need a finger
 * held on the screen.
 */
class HoldOrTap(private val tapMaxMs: Long = TAP_MAX_MS) {

    enum class Action { NONE, START, STOP, CANCEL }

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
        if (nowMs - downAt < tapMaxMs) {
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
