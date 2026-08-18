package com.voxscribe.android

import android.content.Intent
import android.content.res.ColorStateList
import android.inputmethodservice.InputMethodService
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.view.MotionEvent
import android.view.View
import android.view.inputmethod.EditorInfo
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.core.content.ContextCompat
import com.google.android.material.button.MaterialButton
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * VoxScribe's Android equivalent of the desktop app's hold-to-talk flow.
 *
 * Desktop VoxScribe: hold F9 anywhere -> record -> transcribe locally with
 * faster-whisper -> keyboard.write() the cleaned text into whatever window
 * has focus.
 *
 * Android has no equivalent of a global system hotkey that can inject text
 * into an arbitrary focused control, so this is built as a custom software
 * keyboard (an InputMethodService / IME) instead: the user switches to the
 * "VoxScribe" keyboard from any app's keyboard picker, and pressing/holding
 * the mic button records, transcribes, and commits text directly into
 * whatever text field is currently focused -- the same practical result as
 * the desktop app, using the mechanism Android actually provides for it.
 *
 * Two transcription paths, chosen automatically per recording:
 *   - MILESTONE 2 (preferred): [WhisperEngine], a bundled on-device Whisper
 *     model via sherpa-onnx -- the real match to faster-whisper on desktop,
 *     no dependency on device settings. Used whenever the model assets it
 *     needs are present (see WhisperEngine's doc comment).
 *   - MILESTONE 1 (fallback): Android's built-in SpeechRecognizer with
 *     EXTRA_PREFER_OFFLINE=true. Used automatically whenever the bundled
 *     Whisper model isn't available yet, so the keyboard still works before
 *     (or without) doing Milestone 2's manual asset setup.
 */
class VoxScribeInputMethodService : InputMethodService(), RecognitionListener {

    private var speechRecognizer: SpeechRecognizer? = null
    private var audioRecord: AudioRecord? = null
    private var captureThread: Thread? = null
    @Volatile private var capturing = false
    private var usingWhisper = false
    private var isRecording = false
    private lateinit var statusText: TextView
    private lateinit var micButton: MaterialButton
    private val mainHandler = Handler(Looper.getMainLooper())

    override fun onCreateInputView(): View {
        val view = layoutInflater.inflate(R.layout.keyboard_view, null)

        statusText = view.findViewById(R.id.status_text)
        micButton = view.findViewById(R.id.mic_button)
        val backspaceButton = view.findViewById<Button>(R.id.backspace_button)
        val spaceButton = view.findViewById<Button>(R.id.space_button)
        val enterButton = view.findViewById<Button>(R.id.enter_button)
        val switchButton = view.findViewById<Button>(R.id.switch_keyboard_button)

        // Hold-to-talk: press down starts recording, release stops it and
        // triggers transcription -- mirrors the desktop app's F9 behavior.
        micButton.setOnTouchListener { _, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    startListening()
                    true
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    stopListening()
                    true
                }
                else -> false
            }
        }

        backspaceButton.setOnClickListener {
            currentInputConnection?.deleteSurroundingText(1, 0)
        }
        spaceButton.setOnClickListener {
            currentInputConnection?.commitText(" ", 1)
        }
        enterButton.setOnClickListener {
            // Some apps only register the newline on a matching ACTION_UP --
            // sending ACTION_DOWN alone is a key press with no release.
            currentInputConnection?.sendKeyEvent(
                android.view.KeyEvent(android.view.KeyEvent.ACTION_DOWN, android.view.KeyEvent.KEYCODE_ENTER)
            )
            currentInputConnection?.sendKeyEvent(
                android.view.KeyEvent(android.view.KeyEvent.ACTION_UP, android.view.KeyEvent.KEYCODE_ENTER)
            )
        }
        switchButton.setOnClickListener {
            switchToPreviousInputMethod()
        }

        return view
    }

    override fun onStartInputView(info: EditorInfo?, restarting: Boolean) {
        super.onStartInputView(info, restarting)
        if (!hasRecordAudioPermission()) {
            statusText.text = getString(R.string.status_need_permission)
            val intent = Intent(this, PermissionActivity::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            startActivity(intent)
        } else {
            statusText.text = readyStatusText()
        }
    }

    /**
     * Swaps the mic button between its idle (violet, mic icon) and
     * recording (red, stop icon) MD3 states -- deliberately red rather than
     * green, matching the same "mic is hot" convention fix already made on
     * the desktop landing page.
     */
    private fun setMicRecordingVisual(recording: Boolean) {
        val iconRes = if (recording) R.drawable.ic_stop else R.drawable.ic_mic
        val bgColorRes = if (recording) R.color.vox_error else R.color.vox_primary
        val onColorRes = if (recording) R.color.vox_on_error else R.color.vox_on_primary
        val descRes = if (recording) R.string.desc_mic_recording else R.string.desc_mic_idle

        micButton.setIconResource(iconRes)
        val onColor = ColorStateList.valueOf(ContextCompat.getColor(this, onColorRes))
        micButton.iconTint = onColor
        micButton.setTextColor(onColor)
        micButton.backgroundTintList = ColorStateList.valueOf(ContextCompat.getColor(this, bgColorRes))
        micButton.contentDescription = getString(descRes)
    }

    private fun readyStatusText(): String =
        if (WhisperEngine.isAvailable(this)) getString(R.string.status_ready_whisper)
        else getString(R.string.status_ready)

    private fun hasRecordAudioPermission(): Boolean {
        return androidx.core.content.ContextCompat.checkSelfPermission(
            this, android.Manifest.permission.RECORD_AUDIO
        ) == android.content.pm.PackageManager.PERMISSION_GRANTED
    }

    private fun startListening() {
        if (isRecording) return
        if (!hasRecordAudioPermission()) {
            Toast.makeText(this, R.string.status_need_permission, Toast.LENGTH_SHORT).show()
            return
        }

        isRecording = true
        statusText.text = getString(R.string.status_listening)
        micButton.text = getString(R.string.mic_button_recording)
        setMicRecordingVisual(recording = true)

        if (WhisperEngine.isAvailable(this)) {
            startWhisperCapture()
        } else {
            startFallbackRecognizer()
        }
    }

    private fun stopListening() {
        if (!isRecording) return
        isRecording = false
        micButton.text = getString(R.string.mic_button_idle)
        setMicRecordingVisual(recording = false)
        statusText.text = getString(R.string.status_transcribing)

        if (usingWhisper) {
            // The capture thread notices `capturing = false`, stops/releases
            // the AudioRecord, transcribes, and posts the result back to the
            // main thread itself -- nothing more to do here.
            capturing = false
        } else {
            speechRecognizer?.stopListening()
        }
    }

    // --- Milestone 2: bundled Whisper via sherpa-onnx -----------------------------------

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
            statusText.text = getString(R.string.status_no_recognizer)
            isRecording = false
            micButton.text = getString(R.string.mic_button_idle)
            setMicRecordingVisual(recording = false)
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
            record.stop()
            record.release()

            val samples = pcm16BytesToFloat(pcmBytes.toByteArray())
            val cleaned = TranscriptCleanup.clean(WhisperEngine.transcribe(samples))
            mainHandler.post {
                if (cleaned.isNotBlank()) {
                    currentInputConnection?.commitText("$cleaned ", 1)
                }
                statusText.text = readyStatusText()
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

        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            statusText.text = getString(R.string.status_no_recognizer)
            isRecording = false
            micButton.text = getString(R.string.mic_button_idle)
            setMicRecordingVisual(recording = false)
            return
        }

        speechRecognizer?.destroy()
        speechRecognizer = SpeechRecognizer.createSpeechRecognizer(this).also {
            it.setRecognitionListener(this)
        }

        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true)
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
        }
        speechRecognizer?.startListening(intent)
    }

    // --- RecognitionListener callbacks (Milestone 1 path only) -------------------------

    override fun onResults(results: Bundle?) {
        val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
        val raw = matches?.firstOrNull().orEmpty()
        val cleaned = TranscriptCleanup.clean(raw)
        if (cleaned.isNotBlank()) {
            currentInputConnection?.commitText("$cleaned ", 1)
        }
        statusText.text = readyStatusText()
    }

    override fun onError(error: Int) {
        statusText.text = getString(R.string.status_error, error)
        isRecording = false
        micButton.text = getString(R.string.mic_button_idle)
        setMicRecordingVisual(recording = false)
    }

    override fun onPartialResults(partialResults: Bundle?) {}
    override fun onReadyForSpeech(params: Bundle?) {}
    override fun onBeginningOfSpeech() {}
    override fun onRmsChanged(rmsdB: Float) {}
    override fun onBufferReceived(buffer: ByteArray?) {}
    override fun onEndOfSpeech() {
        statusText.text = getString(R.string.status_transcribing)
    }
    override fun onEvent(eventType: Int, params: Bundle?) {}

    override fun onDestroy() {
        super.onDestroy()
        speechRecognizer?.destroy()
        speechRecognizer = null
        capturing = false
        audioRecord?.let {
            if (it.state == AudioRecord.STATE_INITIALIZED) it.stop()
            it.release()
        }
        audioRecord = null
    }
}
