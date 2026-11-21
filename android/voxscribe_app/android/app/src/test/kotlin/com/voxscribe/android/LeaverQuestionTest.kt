package com.voxscribe.android

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate

class LeaverQuestionTest {
    private val today = LocalDate.parse("2026-11-20")

    @Test fun dueAfterFiveQuietDays() {
        assertTrue(LeaverQuestion.isDue(pingOn = true, asked = false, lastUseDay = "2026-11-15", today = today))
    }

    @Test fun notDueBeforeFiveDays() {
        assertFalse(LeaverQuestion.isDue(pingOn = true, asked = false, lastUseDay = "2026-11-16", today = today))
    }

    @Test fun neverAskedTwice() {
        assertFalse(LeaverQuestion.isDue(pingOn = true, asked = true, lastUseDay = "2026-10-01", today = today))
    }

    @Test fun notAskedWithThePingOff() {
        assertFalse(LeaverQuestion.isDue(pingOn = false, asked = false, lastUseDay = "2026-10-01", today = today))
    }

    @Test fun notAskedBeforeAnyDictation() {
        assertFalse(LeaverQuestion.isDue(pingOn = true, asked = false, lastUseDay = null, today = today))
        assertFalse(LeaverQuestion.isDue(pingOn = true, asked = false, lastUseDay = "garbage", today = today))
    }

    @Test fun answerIsSentAsAFixedKeyOnly() {
        val body = Telemetry.payload("id", "1.1.5", "14", "leaver_answer", mapOf("reason" to "too_slow"))
        assertTrue(body.contains("\"event\":\"leaver_answer\""))
        assertTrue(body.contains("\"reason\":\"too_slow\""))
        assertTrue("too_slow" in LeaverQuestion.REASONS)
    }
}
