package com.voxscribe.android

import org.junit.Assert.assertEquals
import org.junit.Test
import kotlin.math.PI
import kotlin.math.sin

/**
 * Granite's front end against values from the model's own Python feature
 * extractor, re-implemented in numpy and checked against it to 0.00004 on the
 * user's real clips (D:\asr_trial\ref.py, 21 Nov 2026).
 */
class GraniteFeaturesTest {
    private fun signal(): FloatArray = FloatArray(20_800) { i ->
        (0.3 * sin(2 * PI * 440 * i / 16000) + 0.1 * sin(2 * PI * 1234 * i / 16000) +
            0.05 * (((i * 7919) % 1000) / 1000.0 - 0.5)).toFloat()
    }

    @Test fun featuresMatchThePythonReference() {
        val f = GraniteEngine.features(signal())
        assertEquals(65, f.size)
        assertEquals(320, f[0].size)
        assertEquals(6190.1138, f.sumOf { row -> row.sumOf { it.toDouble() } }, 0.05)
        assertEquals(1.2409782f, f[0][0], 1e-4f)
        assertEquals(0.0047138f, f[3][100], 1e-4f)
        assertEquals(0.0011453f, f[10][250], 1e-4f)
        assertEquals(0.0021120f, f[64][319], 1e-4f)
        assertEquals(0.2292311f, f[20][5], 1e-4f)
        assertEquals(0.2828348f, f[31][161], 1e-4f)
    }

    @Test fun lettersOfOtherScriptsAreDropped() {
        assertEquals("Send", GraniteEngine.latinOnly("Sendデ"))
        assertEquals("Send it to John.", GraniteEngine.latinOnly("Send 日本 it to John."))
        assertEquals("Ça coûte 5 €, señor. Über!", GraniteEngine.latinOnly("Ça coûte 5 €, señor. Über!"))
        assertEquals("I'm at 10:30 (room 2) & 50%", GraniteEngine.latinOnly("I'm at 10:30 (room 2) & 50%"))
    }

    @Test fun anOddFrameCountIsPaddedToAPair() {
        // 1.01 s: 101 mel frames, padded to 102, so 51 stacked rows.
        assertEquals(51, GraniteEngine.features(FloatArray(16_160) { 0.01f * (it % 7) }).size)
    }
}
