package com.voxscribe.android

import kotlin.math.max
import kotlin.math.sqrt

/**
 * Cuts a running microphone stream into phrases for hands-free mode: a phrase
 * ends when the speaker pauses for [silenceMs]. Loudness based, with a noise
 * floor that follows the room, so a quiet headset and a loud street both work.
 *
 * Feed it audio as it arrives; it returns the phrases that just finished.
 * Pure Kotlin with no Android calls, so it is unit tested directly.
 */
class PhraseSplitter(
    private val sampleRate: Int = 16_000,
    private val frameMs: Int = 30,
    private val silenceMs: Int = 900,
    private val minSpeechMs: Int = 300,
    private val maxPhraseMs: Int = 25_000,
    private val preRollMs: Int = 300,
    private val idleMs: Long = 120_000,
    /** The quietest level that can count as speech, whatever the room does. */
    private val minThreshold: Float = 0.006f,
) {
    private val frameSize = sampleRate * frameMs / 1000
    private val pending = FloatArray(frameSize)
    private var pendingCount = 0

    private val preRoll = ArrayDeque<FloatArray>()
    private val preRollFrames = preRollMs / frameMs
    private val phrase = ArrayList<FloatArray>()
    private var inPhrase = false
    private var speechFrames = 0
    private var silenceFrames = 0
    private var noiseFloor = -1f
    private var msSinceSpeech = 0L

    /** True once nobody has spoken for [idleMs]: hands-free ends by itself then. */
    val idleTimedOut: Boolean get() = !inPhrase && msSinceSpeech >= idleMs

    fun feed(samples: FloatArray, length: Int = samples.size): List<FloatArray> {
        val done = ArrayList<FloatArray>()
        var i = 0
        while (i < length) {
            val take = minOf(frameSize - pendingCount, length - i)
            System.arraycopy(samples, i, pending, pendingCount, take)
            pendingCount += take
            i += take
            if (pendingCount == frameSize) {
                pendingCount = 0
                frame(pending.copyOf())?.let { done.add(it) }
            }
        }
        return done
    }

    /** What is left when listening stops: the phrase in progress, if it held enough speech. */
    fun flush(): FloatArray? {
        val result = if (inPhrase) endPhrase() else null
        inPhrase = false
        return result
    }

    private fun frame(frame: FloatArray): FloatArray? {
        val rms = rms(frame)
        if (noiseFloor < 0f) noiseFloor = rms
        val threshold = max(noiseFloor * 3f, minThreshold)
        val speech = rms >= threshold
        // The floor only learns from quiet frames, so speech does not raise it.
        if (!speech) noiseFloor = noiseFloor * 0.95f + rms * 0.05f

        if (!inPhrase) {
            if (speech) {
                inPhrase = true
                phrase.clear()
                phrase.addAll(preRoll)
                preRoll.clear()
                phrase.add(frame)
                speechFrames = 1
                silenceFrames = 0
                msSinceSpeech = 0
            } else {
                preRoll.addLast(frame)
                while (preRoll.size > preRollFrames) preRoll.removeFirst()
                msSinceSpeech += frameMs
            }
            return null
        }

        phrase.add(frame)
        if (speech) {
            speechFrames++
            silenceFrames = 0
            msSinceSpeech = 0
        } else {
            silenceFrames++
            msSinceSpeech += frameMs
        }
        val paused = silenceFrames * frameMs >= silenceMs
        val tooLong = phrase.size * frameMs >= maxPhraseMs
        if (!paused && !tooLong) return null
        inPhrase = false
        return endPhrase()
    }

    /** The phrase so far, or null when it was only a click or a cough. */
    private fun endPhrase(): FloatArray? {
        val frames = ArrayList(phrase)
        phrase.clear()
        if (speechFrames * frameMs < minSpeechMs) return null
        val out = FloatArray(frames.size * frameSize)
        frames.forEachIndexed { index, f -> System.arraycopy(f, 0, out, index * frameSize, frameSize) }
        return out
    }

    private fun rms(frame: FloatArray): Float {
        var sum = 0.0
        for (s in frame) sum += s.toDouble() * s
        return sqrt(sum / frame.size).toFloat()
    }

    companion object {
        /** "stop listening" said on its own ends hands-free instead of being typed. */
        fun isStopCommand(raw: String): Boolean {
            val words = raw.lowercase().replace(Regex("[^a-z ]"), " ").trim().split(Regex("\\s+"))
            return words.size <= 3 && words.joinToString(" ").contains("stop listening")
        }
    }
}
