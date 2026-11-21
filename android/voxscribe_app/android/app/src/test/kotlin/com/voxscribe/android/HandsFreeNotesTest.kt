package com.voxscribe.android

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.TimeZone
import kotlin.math.PI
import kotlin.math.sin

class PhraseSplitterTest {
    private val rate = 16_000

    private fun silence(ms: Int, level: Float = 0.001f) =
        FloatArray(rate * ms / 1000) { if (it % 2 == 0) level else -level }

    private fun speech(ms: Int, amp: Float = 0.1f) =
        FloatArray(rate * ms / 1000) { (amp * sin(2 * PI * 220 * it / rate)).toFloat() }

    private fun PhraseSplitter.feedAll(vararg parts: FloatArray): List<FloatArray> =
        parts.flatMap { feed(it) }

    @Test
    fun aPauseEndsAPhrase() {
        val s = PhraseSplitter()
        val phrases = s.feedAll(silence(500), speech(800), silence(1000))
        assertEquals(1, phrases.size)
        // The speech, the kept lead-in and the pause that ended it.
        assertTrue(phrases[0].size >= rate * 800 / 1000)
    }

    @Test
    fun twoPhrasesWithAPauseBetweenComeOutInOrder() {
        val s = PhraseSplitter()
        val phrases = s.feedAll(silence(400), speech(600, 0.1f), silence(1000), speech(600, 0.2f), silence(1000))
        assertEquals(2, phrases.size)
        assertTrue(phrases[1].max() > phrases[0].max())
    }

    @Test
    fun aShortBreathInsideAPhraseDoesNotCutIt() {
        val s = PhraseSplitter()
        val phrases = s.feedAll(silence(400), speech(500), silence(400), speech(500), silence(1000))
        assertEquals(1, phrases.size)
    }

    @Test
    fun aClickIsNotAPhrase() {
        val s = PhraseSplitter()
        assertTrue(s.feedAll(silence(400), speech(90), silence(1200)).isEmpty())
    }

    @Test
    fun aQuietHeadsetStillCounts() {
        val s = PhraseSplitter()
        assertEquals(1, s.feedAll(silence(500, 0.0005f), speech(700, 0.02f), silence(1000, 0.0005f)).size)
    }

    @Test
    fun aLongMonologueIsCutSoItTypesInPieces() {
        val s = PhraseSplitter(maxPhraseMs = 3000)
        assertEquals(2, s.feedAll(silence(300), speech(6500)).size)
    }

    @Test
    fun flushHandsBackThePhraseInProgress() {
        val s = PhraseSplitter()
        assertTrue(s.feedAll(silence(300), speech(700)).isEmpty())
        assertNotNull(s.flush())
        assertNull(s.flush())
    }

    @Test
    fun twoQuietMinutesEndIt() {
        val s = PhraseSplitter(idleMs = 2000)
        s.feed(silence(1500))
        assertFalse(s.idleTimedOut)
        s.feed(silence(600))
        assertTrue(s.idleTimedOut)
    }

    @Test
    fun speakingResetsTheQuietClock() {
        val s = PhraseSplitter(idleMs = 2000)
        s.feedAll(silence(1500), speech(500), silence(1000))
        assertFalse(s.idleTimedOut)
    }

    @Test
    fun audioArrivingInOddSizedChunksIsTheSame() {
        val whole = PhraseSplitter().feedAll(silence(400), speech(700), silence(1000))
        val chunked = PhraseSplitter()
        val all = silence(400) + speech(700) + silence(1000)
        val out = ArrayList<FloatArray>()
        var i = 0
        while (i < all.size) {
            val n = minOf(777, all.size - i)
            out += chunked.feed(all.copyOfRange(i, i + n))
            i += n
        }
        assertEquals(whole.size, out.size)
        assertEquals(whole[0].size, out[0].size)
    }

    @Test
    fun stopListeningEndsHandsFreeOnlyWhenSaidOnItsOwn() {
        assertTrue(PhraseSplitter.isStopCommand("Stop listening."))
        assertTrue(PhraseSplitter.isStopCommand("okay, stop listening"))
        assertFalse(PhraseSplitter.isStopCommand("Please tell him to stop listening to that podcast"))
        assertFalse(PhraseSplitter.isStopCommand("stop"))
    }
}

class NotesStoreTest {
    private val utc = TimeZone.getTimeZone("UTC")

    @Test
    fun markdownMatchesTheWindowsInbox() {
        val day1 = 1_793_000_000_000L // 2026-10-26 07:33 UTC
        val notes = listOf(
            Note(3, "Second day", day1 + 86_400_000L),
            Note(2, "Idea: show unsure words", day1 + 8 * 60_000L),
            Note(1, "Call the clinic", day1),
        )
        val expected = """
            # VoxScribe Inbox

            ## 2026-10-26
            - 07:33 Call the clinic
            - 07:41 Idea: show unsure words

            ## 2026-10-27
            - 07:33 Second day

        """.trimIndent()
        assertEquals(expected, NotesStore.markdown(notes, utc))
    }

    @Test
    fun aNoteIsOneLine() {
        assertEquals("buy milk and eggs", NotesStore.oneLine("  buy milk\n and   eggs "))
        assertEquals("", NotesStore.oneLine(" \n "))
    }

    @Test
    fun anEmptyInboxIsJustTheTitle() {
        assertEquals("# VoxScribe Inbox\n", NotesStore.markdown(emptyList(), utc))
    }
}
