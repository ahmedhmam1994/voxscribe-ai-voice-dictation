package com.voxscribe.android

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TelemetryTest {
    @Test
    fun sendsOnceADayAndNeverWhenTurnedOff() {
        assertTrue(Telemetry.shouldSend(enabled = true, lastSentDay = null, today = "2026-10-17"))
        assertTrue(Telemetry.shouldSend(enabled = true, lastSentDay = "2026-10-16", today = "2026-10-17"))
        assertFalse(Telemetry.shouldSend(enabled = true, lastSentDay = "2026-10-17", today = "2026-10-17"))
        assertFalse(Telemetry.shouldSend(enabled = false, lastSentDay = null, today = "2026-10-17"))
    }

    @Test
    fun theEventHoldsOnlyTheVersionsAndTheRandomId() {
        val body = Telemetry.payload("1b2c", "1.1.0", "14")
        assertTrue(body.contains("\"event\":\"app_launched\""))
        assertTrue(body.contains("\"distinct_id\":\"1b2c\""))
        assertTrue(
            body.contains(
                "\"properties\":{\"app_version\":\"1.1.0\",\"os\":\"Android\",\"os_version\":\"14\",\"platform\":\"android\"}",
            ),
        )
    }

    @Test
    fun theFirstDictationSendsBothEventsAndLaterOnesOnlyTheDailyOne() {
        assertEquals(
            listOf("first_dictation", "dictated_today"),
            Telemetry.eventsForDictation(enabled = true, firstSent = false, lastDay = null, today = "2026-10-22"),
        )
        assertEquals(
            listOf("dictated_today"),
            Telemetry.eventsForDictation(enabled = true, firstSent = true, lastDay = "2026-10-21", today = "2026-10-22"),
        )
        assertEquals(
            emptyList<String>(),
            Telemetry.eventsForDictation(enabled = true, firstSent = true, lastDay = "2026-10-22", today = "2026-10-22"),
        )
    }

    @Test
    fun noDictationEventGoesOutWhileThePingIsOff() {
        assertEquals(
            emptyList<String>(),
            Telemetry.eventsForDictation(enabled = false, firstSent = false, lastDay = null, today = "2026-10-22"),
        )
    }

    @Test
    fun aDictationEventCarriesItsNameAndNothingMore() {
        val body = Telemetry.payload("1b2c", "1.1.2", "14", "first_dictation")
        assertTrue(body.contains("\"event\":\"first_dictation\""))
        assertTrue(
            body.contains(
                "\"properties\":{\"app_version\":\"1.1.2\",\"os\":\"Android\",\"os_version\":\"14\",\"platform\":\"android\"}",
            ),
        )
    }

    @Test
    fun oddCharactersCannotBreakTheJson() {
        val body = Telemetry.payload("a\"b", "1.1.0\\x", "14\n")
        assertTrue(body.contains("\"distinct_id\":\"a\\\"b\""))
        assertTrue(body.contains("\"app_version\":\"1.1.0\\\\x\""))
        assertEquals(-1, body.indexOf('\n'))
    }
}
