package com.voxscribe.android

import android.content.Context
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Handler
import android.os.Looper
import android.util.Log
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.FutureTask
import java.util.concurrent.TimeUnit
import kotlin.math.sqrt

/**
 * The hold-to-talk recording + transcription pipeline, shared between
 * BubbleService (floating-bubble mode), kept separate from the service so
 * the pipeline has a single owner and no UI dependencies.
 *
 * Records 16 kHz audio and hands it to [SpeechEngine], which runs the
 * downloaded model for the chosen language on the phone. When that model is
 * not downloaded yet, [startListening] reports why through [onFailure]
 * instead of recording.
 *
 * Deliberately knows nothing about UI: callers own their own status
 * text/button visuals around calling startListening()/stopListening(),
 * this class only reports back via [onResult]/[onFailure].
 */
/**
 * Callers must have already verified RECORD_AUDIO is granted before calling
 * [startListening] (BubbleService does this
 * itself first) -- lint can't see across that call boundary, so
 * the AudioRecord construction below is annotated rather than left as a
 * bare MissingPermission error.
 */
class DictationEngine(
    private val context: Context,
    private val onResult: (String) -> Unit,
    // A message for the user: no microphone, or the model is not ready.
    private val onFailure: (String) -> Unit,
    // Input level from 0 to 1 while recording, delivered on the main thread.
    private val onLevel: (Float) -> Unit = {},
    // True when the result is typed into another app (the bubble): then spoken
    // editing commands and fill-in templates apply too. The in-app screen only
    // shows text, so it leaves this off.
    private val interactive: Boolean = false,
    // The app that has focus right now, for per-app profiles.
    private val focusedPackage: () -> String? = { null },
    // Delivered instead of [onResult] when the utterance was an editing command
    // or a template prompt, not text to type.
    private val onSpecial: (Spoken) -> Unit = {},
    // Called after the text of "how are you? send it" has been delivered.
    private val onSend: (VoiceCommands.SendKind) -> Unit = {},
    // Hands-free only: listening ended (a tap, "stop listening" or two quiet minutes)
    // and every phrase has been delivered.
    private val onHandsFreeEnd: () -> Unit = {},
) {

    private var audioRecord: AudioRecord? = null
    // Guards audioRecord: the capture thread (its own cleanup at the end of
    // startCapture's loop) and destroy() (called from the main
    // thread, e.g. on a fast bubble tap) can otherwise race to stop/release
    // the same AudioRecord, which throws IllegalStateException on the
    // second stop() -- this is exactly the crash a fast tap produced.
    private val recordLock = Any()
    private var captureThread: Thread? = null
    @Volatile private var capturing = false
    @Volatile private var cancelled = false
    private val mainHandler = Handler(Looper.getMainLooper())

    // The names on screen, read while the person talks (see ScreenWords).
    @Volatile private var screenCapture: FutureTask<List<String>>? = null

    @Volatile private var releasedAt = 0L

    /** Why the last dictation had no words, when it had none. Set before the empty result is delivered. */
    @Volatile var noSpeech: NoSpeech? = null
        private set

    // Hands-free: each phrase is cut at a pause and transcribed in order on its own thread.
    @Volatile private var handsFree = false
    private var phraseWorker: java.util.concurrent.ExecutorService? = null

    /**
     * Turns the recording that is running into hands-free listening: from now on
     * every phrase is typed when the speaker pauses. False when it cannot be,
     * because nothing is recording.
     */
    fun startHandsFree(): Boolean {
        if (!capturing) return false
        handsFree = true
        return true
    }

    fun startListening() {
        cancelled = false
        noSpeech = null
        releasedAt = 0L
        FirstRun.step(context, "first_press", once = true)
        if (!SpeechEngine.isInstalled(context)) {
            onFailure(SpeechEngine.notReadyMessage(context))
            return
        }
        screenCapture = if (interactive) FutureTask { ScreenWords.capture(context) }.also { Thread(it).start() } else null
        startCapture()
    }

    fun stopListening() {
        releasedAt = System.currentTimeMillis()
        // The capture thread notices `capturing = false`, stops/releases
        // the AudioRecord, transcribes, and posts the result back to the
        // main thread itself -- nothing more to do here.
        capturing = false
    }

    /**
     * Discards whatever's in flight without delivering a result -- used by
     * BubbleService when a hold-to-talk gesture turns out to have been a
     * drag instead (see its BubbleTouchListener).
     */
    fun cancel() {
        cancelled = true
        capturing = false
    }

    fun destroy() {
        capturing = false
        stopAndReleaseRecord()
    }

    /** Idempotent: safe to call from both the capture thread and destroy(). */
    private fun stopAndReleaseRecord() {
        synchronized(recordLock) {
            val record = audioRecord ?: return
            audioRecord = null
            if (record.recordingState == AudioRecord.RECORDSTATE_RECORDING) record.stop()
            record.release()
        }
    }

    /**
     * Runs the text pipeline (cleanup, voice commands, smart formatting, code
     * dictation, replacements, templates, snippets) on the main thread's behalf
     * and hands the result to the right callback.
     */
    private fun finish(raw: String): Spoken {
        val screen = runCatching { screenCapture?.get(SCREEN_WAIT_MS, TimeUnit.MILLISECONDS) }.getOrNull().orEmpty()
        val spoken = TextPipeline.process(raw, TextPipeline.optionsFor(context, focusedPackage(), screen), interactive)
        if (isDebuggable()) {
            // Debug builds only, so a mis-heard command can be told apart from a bug.
            Log.d("VoxPipeline", "heard=[$raw] interactive=$interactive package=${focusedPackage()} -> ${spoken::class.simpleName}")
        }
        return spoken
    }

    private fun isDebuggable(): Boolean =
        context.applicationInfo.flags and android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE != 0

    private fun deliver(spoken: Spoken) {
        when (spoken) {
            is Spoken.Text -> {
                if (spoken.text.isNotBlank() && releasedAt > 0) {
                    val seconds = (System.currentTimeMillis() - releasedAt) / 1000.0
                    FirstRun.step(context, "first_speed", once = true, extra = mapOf("time" to FirstRun.secondsBucket(seconds)))
                }
                onResult(spoken.text)
                val send = spoken.thenSend
                if (send != null && spoken.text.isNotBlank()) onSend(send)
            }
            else -> onSpecial(spoken)
        }
    }

    // --- Recording ------------------------------------------------------------------

    @Suppress("MissingPermission") // RECORD_AUDIO: see class doc comment
    private fun startCapture() {
        val minBuf = AudioRecord.getMinBufferSize(
            SpeechEngine.SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT
        )
        val bufSize = if (minBuf > 0) minBuf else SpeechEngine.SAMPLE_RATE * 2

        val record = AudioRecord(
            MediaRecorder.AudioSource.VOICE_RECOGNITION,
            SpeechEngine.SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
            bufSize
        )
        if (record.state != AudioRecord.STATE_INITIALIZED) {
            record.release()
            val granted = context.checkSelfPermission(android.Manifest.permission.RECORD_AUDIO) ==
                android.content.pm.PackageManager.PERMISSION_GRANTED
            FirstRun.step(context, "mic_failed", FirstRun.micCode(granted))
            onFailure(context.getString(R.string.status_no_microphone))
            return
        }

        audioRecord = record
        capturing = true
        val pcmBytes = ByteArrayOutputStream()
        record.startRecording()
        FirstRun.step(context, "mic_opened", once = true)

        captureThread = Thread {
            val chunk = ByteArray(bufSize)
            var splitter: PhraseSplitter? = null
            while (capturing) {
                val n = record.read(chunk, 0, chunk.size)
                if (n > 0) {
                    reportLevel(chunk, n)
                    pcmBytes.write(chunk, 0, n)
                    if (handsFree) {
                        val active = splitter ?: PhraseSplitter().also {
                            splitter = it
                            phraseWorker = java.util.concurrent.Executors.newSingleThreadExecutor()
                        }
                        // Everything buffered so far: on the first pass that is what was said
                        // before the tap latched, the start of the first phrase.
                        active.feed(pcm16BytesToFloat(pcmBytes.toByteArray())).forEach(::queuePhrase)
                        pcmBytes.reset()
                        if (active.idleTimedOut) capturing = false
                    }
                }
            }
            stopAndReleaseRecord()

            val hfSplitter = splitter
            if (hfSplitter != null) {
                if (!cancelled) hfSplitter.flush()?.let(::queuePhrase)
                val worker = phraseWorker
                if (worker == null) {
                    mainHandler.post { onHandsFreeEnd() }
                } else {
                    worker.execute { mainHandler.post { onHandsFreeEnd() } }
                    worker.shutdown()
                }
                return@Thread
            }

            if (!cancelled) {
                val samples = pcm16BytesToFloat(pcmBytes.toByteArray())
                // A very fast tap-and-release can reach here with only a
                // handful of samples: nothing usable to transcribe.
                val heldMs = samples.size * 1000L / SpeechEngine.SAMPLE_RATE
                if (heldMs < FirstRun.TAP_MS) FirstRun.step(context, "tap_too_short")
                val peak = samples.maxOfOrNull { kotlin.math.abs(it) } ?: 0f
                if (samples.size < SpeechEngine.SAMPLE_RATE / 4) {
                    noSpeech = NoSpeech.TOO_SHORT
                    mainHandler.post { onResult("") }
                } else {
                    val heard = SpeechEngine.transcribe(context, samples)
                    if (heard == null) {
                        mainHandler.post { onFailure(SpeechEngine.notReadyMessage(context)) }
                        return@Thread
                    }
                    val spoken = TranscriptCleanup.removeNonSpeechTags(heard)
                    if (spoken.isBlank()) noSpeech = NoSpeech.reason(heldMs, peak)
                    if (heldMs >= FirstRun.TAP_MS && spoken.isBlank()) {
                        FirstRun.step(context, "no_speech", extra = mapOf("level" to FirstRun.levelFor(peak)))
                    }
                    val finished = finish(spoken)
                    mainHandler.post { deliver(finished) }
                }
            }
        }.also { it.start() }
    }

    /** Transcribes one hands-free phrase after the ones before it, and types it unless it was "stop listening". */
    private fun queuePhrase(samples: FloatArray) {
        val worker = phraseWorker ?: return
        worker.execute {
            if (cancelled) return@execute
            val heard = SpeechEngine.transcribe(context, samples)
            if (heard == null) {
                // The model went away mid-session (deleted, or it failed to load): stop and say why.
                if (capturing) {
                    capturing = false
                    mainHandler.post { onFailure(SpeechEngine.notReadyMessage(context)) }
                }
                return@execute
            }
            val raw = TranscriptCleanup.removeNonSpeechTags(heard)
            if (raw.isBlank()) return@execute
            if (PhraseSplitter.isStopCommand(raw)) {
                capturing = false
                return@execute
            }
            val finished = finish(raw)
            mainHandler.post { deliver(finished) }
        }
    }

    /** Reports the loudness of one PCM16 chunk as a 0 to 1 level. */
    private fun reportLevel(bytes: ByteArray, length: Int) {
        val count = length / 2
        if (count == 0) return
        var sumOfSquares = 0.0
        for (i in 0 until count) {
            val sample = (bytes[2 * i + 1].toInt() shl 8) or (bytes[2 * i].toInt() and 0xFF)
            sumOfSquares += sample.toDouble() * sample
        }
        val rms = sqrt(sumOfSquares / count) / 32768.0
        // Speech sits well below full scale, so scale it to fill most of the meter.
        val level = (rms * LEVEL_GAIN).coerceIn(0.0, 1.0).toFloat()
        mainHandler.post { onLevel(level) }
    }

    /** Raw little-endian PCM16 bytes (as AudioRecord produces on Android) -> [-1, 1] floats. */
    private fun pcm16BytesToFloat(bytes: ByteArray): FloatArray {
        val shorts = ShortArray(bytes.size / 2)
        ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer().get(shorts)
        return FloatArray(shorts.size) { shorts[it] / 32768.0f }
    }

    private companion object {
        const val LEVEL_GAIN = 6.0
        // The screen was being read the whole time the person talked; this is only for a very busy screen.
        const val SCREEN_WAIT_MS = 400L
    }
}
