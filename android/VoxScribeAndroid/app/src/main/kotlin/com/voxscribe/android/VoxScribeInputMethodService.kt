package com.voxscribe.android

import android.content.Intent
import android.content.res.ColorStateList
import android.inputmethodservice.InputMethodService
import android.view.MotionEvent
import android.view.View
import android.view.inputmethod.EditorInfo
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.core.content.ContextCompat
import com.google.android.material.button.MaterialButton

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
 * The actual recording/transcription pipeline lives in [DictationEngine]
 * (shared with BubbleService's floating-bubble mode, Phase 4) -- see its
 * doc comment for the two transcription paths it chooses between.
 */
class VoxScribeInputMethodService : InputMethodService() {

    private var engine: DictationEngine? = null
    private var isRecording = false
    private lateinit var statusText: TextView
    private lateinit var micButton: MaterialButton

    override fun onCreateInputView(): View {
        // An InputMethodService doesn't reliably inherit the app's manifest
        // theme the way an Activity does -- on some devices/OEM skins the
        // inflater context resolves to a plain system theme instead, which
        // crashes every MaterialButton in the layout at inflate time (they
        // require a Material3 theme to be present on the context). Wrap it
        // explicitly rather than relying on inheritance.
        val themedContext = android.view.ContextThemeWrapper(this, R.style.Theme_VoxScribe)
        val inflater = layoutInflater.cloneInContext(themedContext)
        val view = inflater.inflate(R.layout.keyboard_view, null)

        statusText = view.findViewById(R.id.status_text)
        micButton = view.findViewById(R.id.mic_button)
        val backspaceButton = view.findViewById<Button>(R.id.backspace_button)
        val spaceButton = view.findViewById<Button>(R.id.space_button)
        val enterButton = view.findViewById<Button>(R.id.enter_button)
        val switchButton = view.findViewById<Button>(R.id.switch_keyboard_button)
        val settingsButton = view.findViewById<Button>(R.id.settings_button)

        settingsButton.setOnClickListener {
            startActivity(
                Intent(this, SettingsActivity::class.java).apply {
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                }
            )
        }

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
        if (SettingsStore.preferWhisper(this) && WhisperEngine.isAvailable(this)) getString(R.string.status_ready_whisper)
        else getString(R.string.status_ready)

    private fun hasRecordAudioPermission(): Boolean {
        return androidx.core.content.ContextCompat.checkSelfPermission(
            this, android.Manifest.permission.RECORD_AUDIO
        ) == android.content.pm.PackageManager.PERMISSION_GRANTED
    }

    private fun commitDictatedText(text: String) {
        if (text.isBlank()) return
        val suffix = if (SettingsStore.trailingSpaceEnabled(this)) " " else ""
        currentInputConnection?.commitText(text + suffix, 1)
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

        engine = DictationEngine(
            context = this,
            onResult = { text ->
                commitDictatedText(text)
                statusText.text = readyStatusText()
            },
            onFailure = { message ->
                statusText.text = message
                isRecording = false
                micButton.text = getString(R.string.mic_button_idle)
                setMicRecordingVisual(recording = false)
            },
        ).also { it.startListening() }
    }

    private fun stopListening() {
        if (!isRecording) return
        isRecording = false
        micButton.text = getString(R.string.mic_button_idle)
        setMicRecordingVisual(recording = false)
        statusText.text = getString(R.string.status_transcribing)
        engine?.stopListening()
    }

    override fun onDestroy() {
        super.onDestroy()
        engine?.destroy()
        engine = null
    }
}
