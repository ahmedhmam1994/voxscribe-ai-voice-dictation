package com.voxscribe.android

/**
 * Why a dictation came back with no words, so the user gets advice that fits
 * instead of one "No speech heard" for everything. The key is what the
 * in-app screen receives.
 */
enum class NoSpeech(val key: String) {
    /** Let go before there was anything to hear. */
    TOO_SHORT("too_short"),

    /** The microphone gave almost nothing: muted, blocked, or taken by a call. */
    SILENT("silent"),

    /** Something was heard, but too faint for words. */
    QUIET("quiet"),

    /** Loud enough, but no words came out of it. */
    UNCLEAR("unclear"),
    ;

    companion object {
        /** Under this many milliseconds a recording counts as too short. */
        const val SHORT_MS = 600L

        fun reason(heldMs: Long, peak: Float): NoSpeech = when {
            heldMs < SHORT_MS -> TOO_SHORT
            peak < 0.01f -> SILENT
            peak < 0.05f -> QUIET
            else -> UNCLEAR
        }

        /** The floating button's message, which depends on how it records. */
        fun bubbleMessage(reason: NoSpeech, mode: HoldOrTap.Mode): Int = when (reason) {
            TOO_SHORT -> when (mode) {
                HoldOrTap.Mode.HOLD -> R.string.no_speech_short_hold
                HoldOrTap.Mode.TAP -> R.string.no_speech_short_tap
                HoldOrTap.Mode.BOTH -> R.string.no_speech_short_both
            }
            SILENT -> R.string.no_speech_silent
            QUIET -> R.string.no_speech_quiet
            UNCLEAR -> R.string.no_speech_unclear
        }
    }
}
