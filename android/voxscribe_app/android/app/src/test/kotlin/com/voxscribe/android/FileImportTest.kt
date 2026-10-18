package com.voxscribe.android

import kotlin.math.PI
import kotlin.math.sin
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class FileImportTest {
    private fun tone(sec: Double, amp: Float = 0.2f) =
        FloatArray((sec * 16_000).toInt()) { (amp * sin(2 * PI * 220 * it / 16_000)).toFloat() }

    private fun silence(sec: Double) = FloatArray((sec * 16_000).toInt())

    private fun segments(vararg parts: FloatArray, blockSize: Int = 1000): List<AudioSegment> {
        val out = mutableListOf<AudioSegment>()
        val seg = Segmenter { out.add(it) }
        val all = parts.fold(FloatArray(0)) { a, b -> a + b }
        var i = 0
        while (i < all.size) {
            val n = minOf(blockSize, all.size - i)
            seg.feed(all.copyOfRange(i, i + n))
            i += n
        }
        seg.finish()
        return out
    }

    @Test fun silenceGivesNoPieces() = assertEquals(0, segments(silence(5.0)).size)

    @Test fun twoPhrasesWithAPauseGiveTwoPieces() {
        val out = segments(silence(1.0), tone(2.0), silence(1.5), tone(3.0), silence(1.0))
        assertEquals(2, out.size)
        // The first piece starts shortly before the speech at 1.0 s, not at 0.
        assertTrue(out[0].startSec in 0.8..1.0)
        assertTrue(out[1].startSec in 4.2..4.5)
        assertTrue(out[1].endSec < 7.8)
    }

    @Test fun longSpeechWithoutPausesIsCutBelowTheLimit() {
        val out = segments(tone(30.0))
        assertTrue(out.size >= 3)
        assertTrue(out.all { it.endSec - it.startSec <= Segmenter.MAX_SEGMENT_SEC + 0.1 })
        // Nothing is lost: the pieces cover the whole 30 seconds.
        assertEquals(30.0, out.sumOf { it.endSec - it.startSec }, 0.1)
    }

    @Test fun blockSizeDoesNotChangeTheResult() {
        val a = segments(tone(2.0), silence(1.0), tone(2.0), blockSize = 333)
        val b = segments(tone(2.0), silence(1.0), tone(2.0), blockSize = 4096)
        assertEquals(a.map { it.startSample }, b.map { it.startSample })
    }

    @Test fun captionCardsHaveTwoLinesOfAtMost42Characters() {
        val text = "This is a fairly long sentence that should certainly be split into more than " +
            "one caption card because it goes on and on for quite a while."
        val cues = Captions.cuesFor(10.0, 20.0, text)
        assertTrue(cues.size >= 2)
        for (cue in cues) {
            val lines = cue.text.split("\n")
            assertTrue(lines.size <= 2)
            assertTrue(lines.all { it.length <= 42 })
        }
        assertEquals(10.0, cues.first().startSec, 0.001)
        assertEquals(20.0, cues.last().endSec, 0.001)
        // Cards follow each other without gaps or overlaps.
        cues.zipWithNext().forEach { (a, b) -> assertEquals(a.endSec, b.startSec, 0.001) }
    }

    @Test fun srtFormat() {
        val srt = Captions.srt(listOf(Cue(1.5, 3.25, "Hello there"), Cue(3725.0, 3726.0, "Later")))
        assertEquals(
            "1\n00:00:01,500 --> 00:00:03,250\nHello there\n\n2\n01:02:05,000 --> 01:02:06,000\nLater\n\n",
            srt,
        )
    }

    @Test fun neverOverwrites() {
        assertEquals("talk.srt", Captions.freeName("talk.mp4", "srt", emptySet()))
        assertEquals("talk (2).srt", Captions.freeName("talk.mp4", "srt", setOf("talk.srt")))
        assertEquals("talk (3).srt", Captions.freeName("talk.mp4", "srt", setOf("talk.srt", "talk (2).srt")))
    }
}
