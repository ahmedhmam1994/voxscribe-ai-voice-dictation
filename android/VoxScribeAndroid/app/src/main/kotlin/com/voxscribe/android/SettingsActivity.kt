package com.voxscribe.android

import android.Manifest
import android.app.AlertDialog
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.google.android.material.button.MaterialButton
import com.google.android.material.materialswitch.MaterialSwitch
import com.google.android.material.textview.MaterialTextView
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * Settings + diagnostics screen. Reachable from the keyboard's gear icon
 * (VoxScribeInputMethodService) and gives real, functional options
 * (SettingsStore) plus a read-only status section so it's possible to tell
 * what's actually happening -- which engine is active, whether the bundled
 * Whisper model actually loaded, whether the keyboard is enabled -- without
 * leaving the app or guessing from the keyboard's one-line status text.
 */
class SettingsActivity : AppCompatActivity() {

    private val recordAudioRequestCode = 3001
    private val mainHandler = Handler(Looper.getMainLooper())

    private lateinit var statusText: MaterialTextView
    private lateinit var preferWhisperSwitch: MaterialSwitch
    private lateinit var fallbackLanguageButton: MaterialButton
    private lateinit var cleanupSwitch: MaterialSwitch
    private lateinit var trailingSpaceSwitch: MaterialSwitch
    private lateinit var testWhisperButton: MaterialButton

    private var testRecordThread: Thread? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_settings)

        statusText = findViewById(R.id.status_text)
        preferWhisperSwitch = findViewById(R.id.prefer_whisper_switch)
        fallbackLanguageButton = findViewById(R.id.fallback_language_button)
        cleanupSwitch = findViewById(R.id.cleanup_switch)
        trailingSpaceSwitch = findViewById(R.id.trailing_space_switch)
        testWhisperButton = findViewById(R.id.test_whisper_button)

        preferWhisperSwitch.isChecked = SettingsStore.preferWhisper(this)
        preferWhisperSwitch.setOnCheckedChangeListener { _, checked ->
            SettingsStore.setPreferWhisper(this, checked)
        }

        cleanupSwitch.isChecked = SettingsStore.cleanupEnabled(this)
        cleanupSwitch.setOnCheckedChangeListener { _, checked ->
            SettingsStore.setCleanupEnabled(this, checked)
        }

        trailingSpaceSwitch.isChecked = SettingsStore.trailingSpaceEnabled(this)
        trailingSpaceSwitch.setOnCheckedChangeListener { _, checked ->
            SettingsStore.setTrailingSpaceEnabled(this, checked)
        }

        updateFallbackLanguageButtonText()
        fallbackLanguageButton.setOnClickListener { showLanguagePicker() }

        testWhisperButton.setOnClickListener { runWhisperTest() }

        refreshStatus()
    }

    override fun onResume() {
        super.onResume()
        refreshStatus()
    }

    private fun updateFallbackLanguageButtonText() {
        val current = SettingsStore.fallbackLanguage(this)
        val label = SettingsStore.FALLBACK_LANGUAGES.firstOrNull { it.first == current }?.second
            ?: "System default"
        fallbackLanguageButton.text = getString(R.string.settings_fallback_language) + ": " + label
    }

    private fun showLanguagePicker() {
        val labels = SettingsStore.FALLBACK_LANGUAGES.map { it.second }.toTypedArray()
        val current = SettingsStore.fallbackLanguage(this)
        val currentIndex = SettingsStore.FALLBACK_LANGUAGES.indexOfFirst { it.first == current }.coerceAtLeast(0)

        AlertDialog.Builder(this)
            .setTitle(R.string.settings_fallback_language)
            .setSingleChoiceItems(labels, currentIndex) { dialog, which ->
                SettingsStore.setFallbackLanguage(this, SettingsStore.FALLBACK_LANGUAGES[which].first)
                updateFallbackLanguageButtonText()
                dialog.dismiss()
            }
            .setNegativeButton(android.R.string.cancel, null)
            .show()
    }

    private fun refreshStatus() {
        val hasMicPermission = ContextCompat.checkSelfPermission(
            this, Manifest.permission.RECORD_AUDIO
        ) == PackageManager.PERMISSION_GRANTED

        val enabledInputMethods = Settings.Secure.getString(
            contentResolver, Settings.Secure.ENABLED_INPUT_METHODS
        ) ?: ""
        val keyboardEnabled = enabledInputMethods.contains(packageName)

        val yes = getString(R.string.settings_status_yes)
        val no = getString(R.string.settings_status_no)

        statusText.text = buildString {
            append(getString(R.string.settings_mic_permission)).append(": ")
            append(if (hasMicPermission) yes else no).append('\n')
            append(getString(R.string.settings_keyboard_enabled)).append(": ")
            append(if (keyboardEnabled) yes else no).append('\n')
            append(WhisperEngine.statusDescription(this@SettingsActivity))
        }

        testWhisperButton.isEnabled = hasMicPermission
    }

    // --- Test Whisper: records a fixed 3s clip and shows the transcript ----------------

    private fun runWhisperTest() {
        if (!WhisperEngine.isAvailable(this)) {
            AlertDialog.Builder(this)
                .setTitle(R.string.settings_test_result_title)
                .setMessage(WhisperEngine.statusDescription(this))
                .setPositiveButton(android.R.string.ok, null)
                .show()
            return
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.RECORD_AUDIO), recordAudioRequestCode)
            return
        }

        testWhisperButton.isEnabled = false
        testWhisperButton.text = getString(R.string.settings_test_whisper_recording)

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
            resetTestButton()
            AlertDialog.Builder(this)
                .setTitle(R.string.settings_test_result_title)
                .setMessage("Could not open the microphone.")
                .setPositiveButton(android.R.string.ok, null)
                .show()
            return
        }

        val pcmBytes = ByteArrayOutputStream()
        record.startRecording()
        val recordMillis = 3000L
        val startedAt = System.currentTimeMillis()

        testRecordThread = Thread {
            val chunk = ByteArray(bufSize)
            while (System.currentTimeMillis() - startedAt < recordMillis) {
                val n = record.read(chunk, 0, chunk.size)
                if (n > 0) pcmBytes.write(chunk, 0, n)
            }
            record.stop()
            record.release()

            mainHandler.post { testWhisperButton.text = getString(R.string.settings_test_whisper_transcribing) }

            val shorts = ShortArray(pcmBytes.size() / 2)
            ByteBuffer.wrap(pcmBytes.toByteArray()).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer().get(shorts)
            val samples = FloatArray(shorts.size) { shorts[it] / 32768.0f }
            val text = WhisperEngine.transcribe(samples)

            mainHandler.post {
                resetTestButton()
                AlertDialog.Builder(this)
                    .setTitle(R.string.settings_test_result_title)
                    .setMessage(text.ifBlank { "(no speech detected)" })
                    .setPositiveButton(android.R.string.ok, null)
                    .show()
            }
        }.also { it.start() }
    }

    private fun resetTestButton() {
        testWhisperButton.isEnabled = true
        testWhisperButton.text = getString(R.string.settings_test_whisper)
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        refreshStatus()
    }

    override fun onDestroy() {
        super.onDestroy()
        testRecordThread = null
    }
}
