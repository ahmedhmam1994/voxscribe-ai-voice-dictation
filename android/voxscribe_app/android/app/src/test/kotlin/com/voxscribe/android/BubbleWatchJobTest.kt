package com.voxscribe.android

import com.voxscribe.android.BubbleWatchJob.Companion.Action
import org.junit.Assert.assertEquals
import org.junit.Test

class BubbleWatchJobTest {

    private fun decide(
        wanted: Boolean = true,
        running: Boolean = false,
        on: Boolean = true,
        connected: Boolean = false,
        notified: Boolean = false,
    ) = BubbleWatchJob.decide(wanted, running, on, connected, notified)

    @Test
    fun stopsWatchingWhenTheUserTurnedItOff() {
        assertEquals(Action.STOP_WATCHING, decide(wanted = false))
        assertEquals(Action.STOP_WATCHING, decide(on = false))
    }

    @Test
    fun leavesARunningButtonAlone() {
        assertEquals(Action.NOTHING, decide(running = true))
    }

    @Test
    fun restartsTheButtonWhenOnlyItStopped() {
        assertEquals(Action.REVIVE, decide(connected = true))
    }

    @Test
    fun notifiesOncePerBreakWhenAccessibilityIsDisconnected() {
        assertEquals(Action.NOTIFY, decide())
        assertEquals(Action.NOTHING, decide(notified = true))
    }
}
