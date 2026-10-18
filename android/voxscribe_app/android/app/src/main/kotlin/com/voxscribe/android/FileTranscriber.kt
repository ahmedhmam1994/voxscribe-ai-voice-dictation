package com.voxscribe.android

import android.content.Context
import android.media.AudioFormat
import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import android.net.Uri
import java.nio.ByteOrder

/** What one file turned into. */
class FileTranscript(val text: String, val cues: List<Cue>) {
    val srt: String get() = Captions.srt(cues)
}

/** Thrown when the user cancels an import. */
class ImportCancelled : Exception()

/**
 * Transcribes an audio or video file on the phone: Android's own decoders
 * turn it into 16 kHz mono audio a block at a time, [Segmenter] cuts it at
 * pauses, and each spoken piece goes through the bundled Whisper model and the
 * same text tools as dictation (cleanup, replacements, ...). Nothing is
 * uploaded, and only one short piece is held in memory at a time, so a long
 * video does not fill the phone's memory.
 */
class FileTranscriber(private val context: Context) {
    @Volatile var cancelled = false

    /** Blocking. [onProgress] gets the position and the length in seconds (length 0 when unknown). */
    fun transcribe(uri: Uri, onProgress: (Double, Double) -> Unit): FileTranscript {
        if (!WhisperEngine.isAvailable(context)) {
            throw IllegalStateException("The speech model is not available on this phone.")
        }
        val options = TextPipeline.optionsFor(context, null)
        val texts = mutableListOf<String>()
        val cues = mutableListOf<Cue>()
        val segmenter = Segmenter { segment ->
            if (cancelled) throw ImportCancelled()
            val raw = TranscriptCleanup.removeNonSpeechTags(WhisperEngine.transcribe(segment.samples))
            val spoken = TextPipeline.process(raw, options, interactive = false)
            val text = (spoken as? Spoken.Text)?.text?.trim().orEmpty()
            if (text.isNotEmpty()) {
                texts.add(text)
                cues.addAll(Captions.cuesFor(segment.startSec, segment.endSec, text))
            }
        }
        decode(uri, segmenter::feed, onProgress)
        segmenter.finish()
        return FileTranscript(texts.joinToString(" "), cues)
    }

    /**
     * Decodes the first audio track to 16 kHz mono floats, handing them out
     * in blocks. Works for whatever the phone can play (mp3, m4a, aac, ogg,
     * wav, flac, and the audio of mp4, mov, webm and mkv videos).
     */
    private fun decode(uri: Uri, onBlock: (FloatArray) -> Unit, onProgress: (Double, Double) -> Unit) {
        val extractor = MediaExtractor()
        extractor.setDataSource(context, uri, null)
        val track = (0 until extractor.trackCount).firstOrNull {
            extractor.getTrackFormat(it).getString(MediaFormat.KEY_MIME)?.startsWith("audio/") == true
        } ?: run {
            extractor.release()
            throw IllegalArgumentException("This file has no sound to transcribe.")
        }
        extractor.selectTrack(track)
        val format = extractor.getTrackFormat(track)
        val durationUs = if (format.containsKey(MediaFormat.KEY_DURATION)) format.getLong(MediaFormat.KEY_DURATION) else 0L
        val codec = MediaCodec.createDecoderByType(format.getString(MediaFormat.KEY_MIME)!!)
        codec.configure(format, null, null, 0)
        codec.start()

        var rate = format.getInteger(MediaFormat.KEY_SAMPLE_RATE)
        var channels = format.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
        var floatPcm = false
        val resampler = Resampler()
        val info = MediaCodec.BufferInfo()
        var inputDone = false
        var outputDone = false
        try {
            while (!outputDone) {
                if (cancelled) throw ImportCancelled()
                if (!inputDone) {
                    val index = codec.dequeueInputBuffer(10_000)
                    if (index >= 0) {
                        val buffer = codec.getInputBuffer(index)!!
                        val size = extractor.readSampleData(buffer, 0)
                        if (size < 0) {
                            codec.queueInputBuffer(index, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                            inputDone = true
                        } else {
                            codec.queueInputBuffer(index, 0, size, extractor.sampleTime, 0)
                            extractor.advance()
                        }
                    }
                }
                val out = codec.dequeueOutputBuffer(info, 10_000)
                when {
                    out == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED -> {
                        val f = codec.outputFormat
                        rate = f.getInteger(MediaFormat.KEY_SAMPLE_RATE)
                        channels = f.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
                        floatPcm = f.containsKey(MediaFormat.KEY_PCM_ENCODING) &&
                            f.getInteger(MediaFormat.KEY_PCM_ENCODING) == AudioFormat.ENCODING_PCM_FLOAT
                    }
                    out >= 0 -> {
                        if (info.size > 0) {
                            val buffer = codec.getOutputBuffer(out)!!.order(ByteOrder.LITTLE_ENDIAN)
                            buffer.position(info.offset)
                            buffer.limit(info.offset + info.size)
                            val mono = toMono(buffer, channels, floatPcm)
                            onBlock(resampler.toTarget(mono, rate))
                            onProgress(info.presentationTimeUs / 1e6, durationUs / 1e6)
                        }
                        codec.releaseOutputBuffer(out, false)
                        if (info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) outputDone = true
                    }
                }
            }
        } finally {
            runCatching { codec.stop() }
            codec.release()
            extractor.release()
        }
    }

    private fun toMono(buffer: java.nio.ByteBuffer, channels: Int, floatPcm: Boolean): FloatArray {
        val ch = channels.coerceAtLeast(1)
        return if (floatPcm) {
            val floats = buffer.asFloatBuffer()
            val frames = floats.remaining() / ch
            FloatArray(frames) { i ->
                var sum = 0f
                for (c in 0 until ch) sum += floats.get(i * ch + c)
                sum / ch
            }
        } else {
            val shorts = buffer.asShortBuffer()
            val frames = shorts.remaining() / ch
            FloatArray(frames) { i ->
                var sum = 0f
                for (c in 0 until ch) sum += shorts.get(i * ch + c) / 32768f
                sum / ch
            }
        }
    }

    /** Linear resampling to 16 kHz that carries its position across blocks, so block edges add no clicks. */
    private class Resampler {
        private var position = 0.0 // in source samples, relative to the start of the next block
        private var previous = 0f

        fun toTarget(input: FloatArray, sourceRate: Int): FloatArray {
            if (sourceRate == Segmenter.RATE) return input
            if (input.isEmpty()) return input
            val step = sourceRate / Segmenter.RATE.toDouble()
            val out = ArrayList<Float>((input.size / step).toInt() + 2)
            while (position < input.size) {
                val i = position.toInt()
                val frac = (position - i).toFloat()
                val a = if (i - 1 < 0) previous else input[i - 1]
                val b = input[i]
                // position counts from one sample before this block, so i-1..i spans the gap.
                out.add(a + (b - a) * frac)
                position += step
            }
            position -= input.size
            previous = input.last()
            return out.toFloatArray()
        }
    }
}
