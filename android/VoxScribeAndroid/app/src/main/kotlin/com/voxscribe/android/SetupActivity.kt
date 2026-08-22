package com.voxscribe.android

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.provider.Settings
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.google.android.material.button.MaterialButton
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
    private lateinit var startBubbleButton: MaterialButton

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_setup)

        statusText = findViewById(R.id.status_text)
        startBubbleButton = findViewById(R.id.start_bubble_button)

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

        findViewById<android.view.View>(R.id.grant_overlay_button).setOnClickListener {
            startActivity(BubblePermissions.overlayPermissionIntent(this))
        }
        findViewById<android.view.View>(R.id.enable_accessibility_button).setOnClickListener {
            startActivity(BubblePermissions.accessibilitySettingsIntent())
        }
        startBubbleButton.setOnClickListener {
            if (BubbleService.isRunning) {
                stopService(Intent(this, BubbleService::class.java))
            } else if (BubblePermissions.hasOverlayPermission(this) &&
                BubblePermissions.isAccessibilityServiceEnabled(this)
            ) {
                ContextCompat.startForegroundService(this, Intent(this, BubbleService::class.java))
            } else {
                Toast.makeText(this, R.string.bubble_missing_permissions, Toast.LENGTH_LONG).show()
            }
            refreshStatus()
        }

        refreshStatus()
    }

    private fun refreshStatus() {
        val hasPermission = ContextCompat.checkSelfPermission(
            this, Manifest.permission.RECORD_AUDIO
        ) == PackageManager.PERMISSION_GRANTED
        refreshBubbleSection()
        statusText.text = buildString {
            append("Mic permission: ")
            append(if (hasPermission) "granted ✓" else "not granted")
            append("\n\nAfter step 2, go to Settings and turn on \"VoxScribe\" as an ")
            append("input method. Then in step 3 (or from any text field's keyboard ")
            append("switcher), pick VoxScribe and hold the mic button to dictate.")
        }
    }

    /**
     * Reflects real permission/service state on the three floating-bubble
     * buttons (checkmarks on steps 1-2, and step 3 switches between
     * Start/Stop and is disabled until the first two are actually granted)
     * instead of the three raw, ungated buttons this section started as.
     */
    private fun refreshBubbleSection() {
        val hasOverlay = BubblePermissions.hasOverlayPermission(this)
        val hasAccessibility = BubblePermissions.isAccessibilityServiceEnabled(this)

        findViewById<MaterialButton>(R.id.grant_overlay_button).setText(
            if (hasOverlay) R.string.setup_grant_overlay_done else R.string.setup_grant_overlay
        )
        findViewById<MaterialButton>(R.id.enable_accessibility_button).setText(
            if (hasAccessibility) R.string.setup_enable_accessibility_done else R.string.setup_enable_accessibility
        )

        startBubbleButton.isEnabled = BubbleService.isRunning || (hasOverlay && hasAccessibility)
        startBubbleButton.setText(
            if (BubbleService.isRunning) R.string.setup_stop_bubble else R.string.setup_start_bubble
        )
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
