package com.voxscribe.android

import org.junit.Assert.assertEquals
import org.junit.Test

class NoSpeechTest {
    @Test
    fun aQuickPressIsTooShortWhateverTheLevel() {
        assertEquals(NoSpeech.TOO_SHORT, NoSpeech.reason(300, 0.5f))
        assertEquals(NoSpeech.TOO_SHORT, NoSpeech.reason(599, 0.0f))
    }

    @Test
    fun aLongerRecordingIsJudgedByHowLoudItWas() {
        assertEquals(NoSpeech.SILENT, NoSpeech.reason(2000, 0.004f))
        assertEquals(NoSpeech.QUIET, NoSpeech.reason(2000, 0.03f))
        assertEquals(NoSpeech.UNCLEAR, NoSpeech.reason(2000, 0.3f))
    }

    @Test
    fun theTooShortAdviceFollowsHowTheButtonRecords() {
        assertEquals(R.string.no_speech_short_hold, NoSpeech.bubbleMessage(NoSpeech.TOO_SHORT, HoldOrTap.Mode.HOLD))
        assertEquals(R.string.no_speech_short_tap, NoSpeech.bubbleMessage(NoSpeech.TOO_SHORT, HoldOrTap.Mode.TAP))
        assertEquals(R.string.no_speech_short_both, NoSpeech.bubbleMessage(NoSpeech.TOO_SHORT, HoldOrTap.Mode.BOTH))
        assertEquals(R.string.no_speech_silent, NoSpeech.bubbleMessage(NoSpeech.SILENT, HoldOrTap.Mode.BOTH))
    }

    @Test
    fun theKeysMatchWhatTheAppScreenExpects() {
        assertEquals(listOf("too_short", "silent", "quiet", "unclear"), NoSpeech.values().map { it.key })
    }
}
