package com.voxscribe.android

import android.content.Context
import android.content.Intent
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * The hold-to-talk recording + transcription pipeline, shared between
 * VoxScribeInputMethodService (keyboard mode) and BubbleService
 * (floating-bubble mode) -- extracted out of the IME, which used to own
 * this logic directly, so the two entry points run the exact same
 * pipeline instead of a second, divergent copy of it.
 *
 * Two transcription paths, chosen automatically per recording:
 *   - MILESTONE 2 (preferred): [WhisperEngine], a bundled on-device Whisper
 *     model via sherpa-onnx -- the real match to faster-whisper on desktop,
 *     no dependency on device settings. Used whenever the model assets it
 *     needs are present (see WhisperEngine's doc comment).
 *   - MILESTONE 1 (fallback): Android's built-in SpeechRecognizer with
 *     EXTRA_PREFER_OFFLINE=true. Used automatically whenever the bundled
 *     Whisper model isn't available yet.
 *
 * Deliberately knows nothing about UI: callers own their own status
 * text/button visuals around calling startListening()/stopListening(),
 * the same way VoxScribeInputMethodService already did before this was
 * extracted -- this class only reports back via [onResult]/[onFailure].
 */
/**
 * Callers must have already verified RECORD_AUDIO is granted before calling
 * [startListening] (both VoxScribeInputMethodService and BubbleService do
 * this themselves first) -- lint can't see across that call boundary, so
 * the AudioRecord construction below is annotated rather than left as a
 * bare MissingPermission error.
 */
class DictationEngine(
    private val context: Context,
    private val onResult: (String) -> Unit,
    // Named onFailure, not onError -- RecognitionListener (implemented
    // below) already requires a member function called onError(Int), and
    // a same-named constructor property here would collide with it.
    private val onFailure: (String) -> Unit,
) : RecognitionListener {

    private var speechRecognizer: SpeechRecognizer? = null
    private var audioRecord: AudioRecord? = null
    // Guards audioRecord: the capture thread (its own cleanup at the end of
    // startWhisperCapture's loop) and destroy() (called from the main
    // thread, e.g. on a fast bubble tap) can otherwise race to stop/release
    // the same AudioRecord, which throws IllegalStateException on the
    // second stop() -- this is exactly the crash a fast tap produced.
    private val recordLock = Any()
    private var captureThread: Thread? = null
    @Volatile private var capturing = false
    @Volatile private var cancelled = false
    private var usingWhisper = false
    private val mainHandler = Handler(Looper.getMainLooper())

    val willUseWhisper: Boolean
        get() = SettingsStore.preferWhisper(context) && WhisperEngine.isAvailable(context)

    fun startListening() {
        cancelled = false
        if (willUseWhisper) startWhisperCapture() else startFallbackRecognizer()
    }

    fun stopListening() {
        if (usingWhisper) {
            // The capture thread notices `capturing = false`, stops/releases
            // the AudioRecord, transcribes, and posts the result back to the
            // main thread itself -- nothing more to do here.
            capturing = false
        } else {
            speechRecognizer?.stopListening()
        }
    }

    /**
     * Discards whatever's in flight without delivering a result -- used by
     * BubbleService when a hold-to-talk gesture turns out to have been a
     * drag instead (see its BubbleTouchListener).
     */
    fun cancel() {
        cancelled = true
        if (usingWhisper) {
            capturing = false
        } else {
            speechRecognizer?.cancel()
        }
    }

    fun destroy() {
        speechRecognizer?.destroy()
        speechRecognizer = null
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

    private fun cleanupIfEnabled(text: String): String =
        if (SettingsStore.cleanupEnabled(context)) TranscriptCleanup.clean(text) else text

    // --- Milestone 2: bundled Whisper via sherpa-onnx -----------------------------------

    @Suppress("MissingPermission") // RECORD_AUDIO: see class doc comment
    private fun startWhisperCapture() {
        usingWhisper = true

        val minBuf = AudioRecord.getMinBufferSize(
            WhisperEngine.SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT
        )
        val bufSize = if (minBuf > 0) minBuf else WhisperEngine.SAMPLE_RATE * 2

        val record = AudioRecord(
            MediaRecorder.AudioSource.VOICE_RECOGNITION,
            WhisperEngine.SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
            bufSize
        )
        if (record.state != AudioRecord.STATE_INITIALIZED) {
            record.release()
            usingWhisper = false
            onFailure(context.getString(R.string.status_no_recognizer))
            return
        }

        audioRecord = record
        capturing = true
        val pcmBytes = ByteArrayOutputStream()
        record.startRecording()

        captureThread = Thread {
            val chunk = ByteArray(bufSize)
            while (capturing) {
                val n = record.read(chunk, 0, chunk.size)
                if (n > 0) pcmBytes.write(chunk, 0, n)
            }
            stopAndReleaseRecord()

            if (!cancelled) {
                val samples = pcm16BytesToFloat(pcmBytes.toByteArray())
                // sherpa-onnx's native decoder segfaults (null deref) on a
                // near-empty buffer -- a very fast tap-and-release can reach
                // here with only a handful of samples. Below this floor
                // there's nothing usable to transcribe anyway.
                if (samples.size < WhisperEngine.SAMPLE_RATE / 4) {
                    mainHandler.post { onResult("") }
                } else {
                    val cleaned = cleanupIfEnabled(WhisperEngine.transcribe(samples))
                    mainHandler.post { onResult(cleaned) }
                }
            }
        }.also { it.start() }
    }

    /** Raw little-endian PCM16 bytes (as AudioRecord produces on Android) -> [-1, 1] floats. */
    private fun pcm16BytesToFloat(bytes: ByteArray): FloatArray {
        val shorts = ShortArray(bytes.size / 2)
        ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer().get(shorts)
        return FloatArray(shorts.size) { shorts[it] / 32768.0f }
    }

    // --- Milestone 1: Android's built-in SpeechRecognizer (fallback) -------------------

    private fun startFallbackRecognizer() {
        usingWhisper = false

        if (!SpeechRecognizer.isRecognitionAvailable(context)) {
            onFailure(context.getString(R.string.status_no_recognizer))
            return
        }

        speechRecognizer?.destroy()
        speechRecognizer = SpeechRecognizer.createSpeechRecognizer(context).also {
            it.setRecognitionListener(this)
        }

        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true)
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
            SettingsStore.fallbackLanguage(context)?.let { lang ->
                putExtra(RecognizerIntent.EXTRA_LANGUAGE, lang)
            }
        }
        speechRecognizer?.startListening(intent)
    }

    // --- RecognitionListener callbacks (Milestone 1 path only) -------------------------

    override fun onResults(results: Bundle?) {
        if (cancelled) return
        val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
        val raw = matches?.firstOrNull().orEmpty()
        onResult(cleanupIfEnabled(raw))
    }

    override fun onError(error: Int) {
        if (cancelled) return
        onFailure(context.getString(R.string.status_error, error))
    }

    override fun onPartialResults(partialResults: Bundle?) {}
    override fun onReadyForSpeech(params: Bundle?) {}
    override fun onBeginningOfSpeech() {}
    override fun onRmsChanged(rmsdB: Float) {}
    override fun onBufferReceived(buffer: ByteArray?) {}
    override fun onEndOfSpeech() {}
    override fun onEvent(eventType: Int, params: Bundle?) {}
}
