package com.voxscribe.android

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class BubbleReviveTest {

    @Test
    fun revivesOnlyWhenWantedStoppedAndAllowed() {
        assertTrue(BubbleRevive.shouldRevive(wanted = true, running = false, overlay = true, accessibility = true, microphone = true))
        assertFalse(BubbleRevive.shouldRevive(wanted = false, running = false, overlay = true, accessibility = true, microphone = true))
        assertFalse(BubbleRevive.shouldRevive(wanted = true, running = true, overlay = true, accessibility = true, microphone = true))
        assertFalse(BubbleRevive.shouldRevive(wanted = true, running = false, overlay = false, accessibility = true, microphone = true))
        assertFalse(BubbleRevive.shouldRevive(wanted = true, running = false, overlay = true, accessibility = false, microphone = true))
        assertFalse(BubbleRevive.shouldRevive(wanted = true, running = false, overlay = true, accessibility = true, microphone = false))
    }

    @Test
    fun returnsToTheAppOnlySoonAfterSetupAsked() {
        val asked = 1_000_000L
        assertTrue(BubbleRevive.returnDue(asked, asked + 30_000L))
        assertFalse(BubbleRevive.returnDue(asked, asked + 11 * 60_000L))
        assertFalse(BubbleRevive.returnDue(0L, asked))
        assertFalse(BubbleRevive.returnDue(asked, asked - 1L))
    }
}
