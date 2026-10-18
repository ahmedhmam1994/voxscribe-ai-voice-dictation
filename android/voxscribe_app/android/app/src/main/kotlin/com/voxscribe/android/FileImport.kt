package com.voxscribe.android

import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

/**
 * Pieces of the file import that need no phone: cutting a long recording into
 * short spoken pieces, turning each piece's text into caption cards, and
 * writing those cards as an .srt file. The Android speech model reads at most
 * about 30 seconds at a time and gives no word timings, so a file is cut at
 * pauses into pieces of up to [Segmenter.MAX_SEGMENT_SEC], and each piece's
 * time span is shared out across its cards by length.
 */

/** One spoken piece of a file: where it starts (in samples at 16 kHz) and its audio. */
class AudioSegment(val startSample: Long, val samples: FloatArray) {
    val startSec: Double get() = startSample / Segmenter.RATE.toDouble()
    val endSec: Double get() = (startSample + samples.size) / Segmenter.RATE.toDouble()
}

/**
 * Takes 16 kHz mono audio in blocks of any size and hands out spoken pieces:
 * a piece ends at a pause of at least [PAUSE_SEC] once it is a second long,
 * or at the quietest moment of its last few seconds when it reaches
 * [MAX_SEGMENT_SEC]. Silence between pieces is dropped, so no time is spent
 * transcribing it (and Whisper cannot invent text for it).
 */
class Segmenter(private val onSegment: (AudioSegment) -> Unit) {
    companion object {
        const val RATE = 16_000
        const val FRAME = 480 // 30 ms
        const val MAX_SEGMENT_SEC = 12.0
        const val MIN_SEGMENT_SEC = 1.0
        const val PAUSE_SEC = 0.4
        const val PAD_SEC = 0.15
        /** RMS above this counts as speech. Quiet recordings are lifted first by [speechThreshold]. */
        const val BASE_THRESHOLD = 0.01f
    }

    private val frame = FloatArray(FRAME)
    private var frameFill = 0
    private var position = 0L // samples seen so far

    // The piece being collected.
    private val current = ArrayList<FloatArray>() // frames
    private val levels = ArrayList<Float>()
    private var currentStart = -1L
    private var silentFrames = 0
    private var loudest = 0f

    // A little audio before speech starts, so first syllables are not cut.
    private val lead = ArrayDeque<FloatArray>()
    private val leadFrames = (PAD_SEC * RATE / FRAME).toInt().coerceAtLeast(1)

    fun feed(block: FloatArray) {
        var i = 0
        while (i < block.size) {
            val n = min(FRAME - frameFill, block.size - i)
            System.arraycopy(block, i, frame, frameFill, n)
            frameFill += n
            i += n
            if (frameFill == FRAME) {
                onFrame(frame.copyOf())
                frameFill = 0
            }
        }
    }

    /** Call at the end of the file to hand out the last piece. */
    fun finish() {
        if (frameFill > 0) {
            onFrame(frame.copyOf(frameFill))
            frameFill = 0
        }
        emit(current.size)
    }

    private fun speechThreshold(): Float = max(BASE_THRESHOLD, loudest * 0.08f)

    private fun onFrame(f: FloatArray) {
        val level = rms(f)
        loudest = max(loudest * 0.9995f, level)
        val speech = level > speechThreshold()
        val frameStart = position
        position += f.size

        if (currentStart < 0) {
            if (!speech) {
                lead.addLast(f)
                if (lead.size > leadFrames) lead.removeFirst()
                return
            }
            currentStart = frameStart - lead.sumOf { it.size }
            for (l in lead) {
                current.add(l)
                levels.add(0f)
            }
            lead.clear()
        }

        current.add(f)
        levels.add(level)
        silentFrames = if (speech) 0 else silentFrames + 1

        val lengthSec = current.size * FRAME / RATE.toDouble()
        val pauseFrames = (PAUSE_SEC * RATE / FRAME).toInt()
        if (silentFrames >= pauseFrames && lengthSec >= MIN_SEGMENT_SEC) {
            // End at the pause, keeping a little of it.
            val keep = current.size - silentFrames + leadFrames
            emit(min(keep, current.size))
        } else if (lengthSec >= MAX_SEGMENT_SEC) {
            // Too long without a pause: cut at the quietest frame of the last 3 seconds.
            val window = (3.0 * RATE / FRAME).toInt()
            val from = max(1, levels.size - window)
            var cut = levels.size
            var quietest = Float.MAX_VALUE
            for (k in from until levels.size) {
                if (levels[k] < quietest) {
                    quietest = levels[k]
                    cut = k
                }
            }
            emit(cut)
        }
    }

    /** Hands out the first [frames] frames of the current piece and keeps the rest as the next one. */
    private fun emit(frames: Int) {
        if (current.isEmpty() || frames <= 0) {
            reset()
            return
        }
        val taken = current.subList(0, frames)
        val total = taken.sumOf { it.size }
        val samples = FloatArray(total)
        var at = 0
        for (f in taken) {
            System.arraycopy(f, 0, samples, at, f.size)
            at += f.size
        }
        val rest = ArrayList(current.subList(frames, current.size))
        val restLevels = ArrayList(levels.subList(frames, levels.size))
        val start = currentStart
        val hadSpeech = levels.subList(0, frames).any { it > speechThreshold() }
        reset()
        if (hadSpeech) onSegment(AudioSegment(start, samples))
        if (rest.isNotEmpty() && restLevels.any { it > speechThreshold() }) {
            currentStart = start + total
            current.addAll(rest)
            levels.addAll(restLevels)
            silentFrames = 0
        }
    }

    private fun reset() {
        current.clear()
        levels.clear()
        currentStart = -1
        silentFrames = 0
    }

    private fun rms(f: FloatArray): Float {
        if (f.isEmpty()) return 0f
        var sum = 0.0
        for (s in f) sum += s * s
        return sqrt(sum / f.size).toFloat()
    }
}

/** One caption card. */
data class Cue(val startSec: Double, val endSec: Double, val text: String)

object Captions {
    const val LINE_CHARS = 42
    const val LINES_PER_CARD = 2

    /**
     * Splits one piece's text into cards of up to two lines of [LINE_CHARS]
     * characters, sharing the piece's time span out by length.
     */
    fun cuesFor(startSec: Double, endSec: Double, text: String): List<Cue> {
        val words = text.trim().split(Regex("\\s+")).filter { it.isNotEmpty() }
        if (words.isEmpty()) return emptyList()
        val cards = mutableListOf<String>()
        val lines = mutableListOf<String>()
        var line = StringBuilder()
        for (word in words) {
            if (line.isNotEmpty() && line.length + 1 + word.length > LINE_CHARS) {
                lines.add(line.toString())
                line = StringBuilder()
                if (lines.size == LINES_PER_CARD) {
                    cards.add(lines.joinToString("\n"))
                    lines.clear()
                }
            }
            if (line.isNotEmpty()) line.append(' ')
            line.append(word)
        }
        if (line.isNotEmpty()) lines.add(line.toString())
        if (lines.isNotEmpty()) cards.add(lines.joinToString("\n"))

        val totalChars = cards.sumOf { it.length }.coerceAtLeast(1)
        val span = (endSec - startSec).coerceAtLeast(0.5)
        val cues = mutableListOf<Cue>()
        var t = startSec
        for ((i, card) in cards.withIndex()) {
            val end = if (i == cards.lastIndex) startSec + span else t + span * card.length / totalChars
            cues.add(Cue(t, end, card))
            t = end
        }
        return cues
    }

    fun timestamp(sec: Double): String {
        val ms = (sec * 1000).toLong().coerceAtLeast(0)
        val h = ms / 3_600_000
        val m = ms / 60_000 % 60
        val s = ms / 1000 % 60
        return "%02d:%02d:%02d,%03d".format(h, m, s, ms % 1000)
    }

    fun srt(cues: List<Cue>): String = buildString {
        cues.forEachIndexed { i, cue ->
            append(i + 1).append('\n')
            append(timestamp(cue.startSec)).append(" --> ").append(timestamp(cue.endSec)).append('\n')
            append(cue.text).append("\n\n")
        }
    }

    /** "talk.mp4" -> "talk.srt"; the same name with " (2)", " (3)" ... when taken. */
    fun freeName(source: String, extension: String, taken: Set<String>): String {
        val base = source.substringBeforeLast('.', source)
        var name = "$base.$extension"
        var n = 2
        while (name.lowercase() in taken) {
            name = "$base ($n).$extension"
            n++
        }
        return name
    }
}
