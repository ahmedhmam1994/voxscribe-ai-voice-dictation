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

    @Test
    fun aNewUserSendsEachSetupStepOnceInOrder() {
        val first = Telemetry.setupEvents(enabled = true, done = emptySet(), handled = null)
        assertEquals(emptyList<String>(), first.send)

        val opened = Telemetry.setupEvents(true, setOf("setup_opened"), first.handled)
        assertEquals(listOf("setup_opened"), opened.send)

        val micAndOverlay = Telemetry.setupEvents(true, setOf("setup_overlay", "setup_microphone"), opened.handled)
        assertEquals(listOf("setup_microphone", "setup_overlay"), micAndOverlay.send)

        val again = Telemetry.setupEvents(true, setOf("setup_microphone", "setup_overlay"), micAndOverlay.handled)
        assertEquals(emptyList<String>(), again.send)
    }

    @Test
    fun anUpdateSendsNothingForStepsDoneBefore() {
        val done = setOf("setup_microphone", "setup_accessibility", "setup_overlay", "bubble_started")
        val first = Telemetry.setupEvents(enabled = true, done = done, handled = null)
        assertEquals(emptyList<String>(), first.send)
        assertTrue("setup_opened" in first.handled)

        assertEquals(emptyList<String>(), Telemetry.setupEvents(true, done + "setup_opened", first.handled).send)
    }

    @Test
    fun setupStepsAreRememberedButNotSentWhileThePingIsOff() {
        val off = Telemetry.setupEvents(enabled = false, done = setOf("setup_microphone"), handled = emptySet())
        assertEquals(emptyList<String>(), off.send)

        val on = Telemetry.setupEvents(true, setOf("setup_microphone", "setup_overlay"), off.handled)
        assertEquals(listOf("setup_overlay"), on.send)
    }
}
