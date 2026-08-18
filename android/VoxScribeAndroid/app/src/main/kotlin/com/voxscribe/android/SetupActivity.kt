package com.voxscribe.android

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.provider.Settings
import android.view.View
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

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

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val statusText = TextView(this).apply {
            textSize = 16f
            setPadding(48, 96, 48, 24)
        }
        val grantPermButton = Button(this).apply { text = "1. Grant microphone permission" }
        val enableKeyboardButton = Button(this).apply { text = "2. Enable VoxScribe keyboard" }
        val pickKeyboardButton = Button(this).apply { text = "3. Switch to VoxScribe keyboard" }

        val layout = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.VERTICAL
            setPadding(48, 48, 48, 48)
            addView(statusText)
            addView(grantPermButton)
            addView(enableKeyboardButton)
            addView(pickKeyboardButton)
        }
        setContentView(layout)

        fun refreshStatus() {
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
        refreshStatus()

        grantPermButton.setOnClickListener {
            ActivityCompat.requestPermissions(
                this, arrayOf(Manifest.permission.RECORD_AUDIO), recordAudioRequestCode
            )
        }
        enableKeyboardButton.setOnClickListener {
            startActivity(Intent(Settings.ACTION_INPUT_METHOD_SETTINGS))
        }
        pickKeyboardButton.setOnClickListener {
            val imm = getSystemService(INPUT_METHOD_SERVICE) as android.view.inputmethod.InputMethodManager
            imm.showInputMethodPicker()
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        recreate()
    }
}
