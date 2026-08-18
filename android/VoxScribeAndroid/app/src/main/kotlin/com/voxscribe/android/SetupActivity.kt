package com.voxscribe.android

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.provider.Settings
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.google.android.material.textview.MaterialTextView

/**
 * The app's only "real" screen. VoxScribe has no main window it needs during
 * normal use (same spirit as the desktop app being tray-first) -- this
 * screen exists purely to walk a first-time user through the two one-off
 * setup steps Android requires for a custom keyboard:
 *   1. Grant the RECORD_AUDIO permission.
 *   2. Enable "VoxScribe" as an input method, then select it from the
 *      keyboard picker in whatever app they want to dictate into.
 */
class SetupActivity : AppCompatActivity() {

    private val recordAudioRequestCode = 2001
    private lateinit var statusText: MaterialTextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_setup)

        statusText = findViewById(R.id.status_text)
        refreshStatus()

        findViewById<android.view.View>(R.id.grant_perm_button).setOnClickListener {
            ActivityCompat.requestPermissions(
                this, arrayOf(Manifest.permission.RECORD_AUDIO), recordAudioRequestCode
            )
        }
        findViewById<android.view.View>(R.id.enable_keyboard_button).setOnClickListener {
            startActivity(Intent(Settings.ACTION_INPUT_METHOD_SETTINGS))
        }
        findViewById<android.view.View>(R.id.pick_keyboard_button).setOnClickListener {
            val imm = getSystemService(INPUT_METHOD_SERVICE) as android.view.inputmethod.InputMethodManager
            imm.showInputMethodPicker()
        }
        findViewById<android.view.View>(R.id.open_settings_button).setOnClickListener {
            startActivity(Intent(this, SettingsActivity::class.java))
        }
    }

    private fun refreshStatus() {
        val hasPermission = ContextCompat.checkSelfPermission(
            this, Manifest.permission.RECORD_AUDIO
        ) == PackageManager.PERMISSION_GRANTED
        statusText.text = buildString {
            append("Mic permission: ")
            append(if (hasPermission) "granted ✓" else "not granted")
            append("\n\nAfter step 2, go to Settings and turn on \"VoxScribe\" as an ")
            append("input method. Then in step 3 (or from any text field's keyboard ")
            append("switcher), pick VoxScribe and hold the mic button to dictate.")
        }
    }

    override fun onResume() {
        super.onResume()
        // Catches the user coming back from the system input-method settings
        // screen (step 2), not just the permission-request callback below.
        refreshStatus()
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        refreshStatus()
    }
}
