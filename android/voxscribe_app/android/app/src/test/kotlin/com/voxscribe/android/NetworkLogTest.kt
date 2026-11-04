package com.voxscribe.android

import org.junit.Assert.assertEquals
import org.junit.Test

class NetworkLogTest {
    @Test fun entriesSurviveSaving() {
        val entries = listOf(
            NetworkLog.Entry(1L, "Update check", "api.github.com", "Nothing about you"),
            NetworkLog.Entry(2L, "Usage ping (first_dictation)", "us.i.posthog.com", "A random id"),
        )
        assertEquals(entries, NetworkLog.decode(NetworkLog.encode(entries)))
    }

    @Test fun tabsAndLineBreaksCannotBreakAnEntry() {
        val saved = NetworkLog.encode(listOf(NetworkLog.Entry(5L, "a\tb", "host", "line\nbreak")))
        assertEquals(listOf(NetworkLog.Entry(5L, "a b", "host", "line break")), NetworkLog.decode(saved))
    }

    @Test fun damagedLinesAreSkipped() {
        assertEquals(emptyList<NetworkLog.Entry>(), NetworkLog.decode("not a number\tx\ty\tz\n\n7\tonly two"))
    }

    @Test fun onlyTheHostIsShown() {
        assertEquals("api.github.com", NetworkLog.hostOf("https://api.github.com/repos/x/releases?per_page=30"))
    }
}
