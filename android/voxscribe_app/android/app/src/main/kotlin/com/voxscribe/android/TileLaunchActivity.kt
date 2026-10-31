package com.voxscribe.android

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import androidx.core.content.ContextCompat

/**
 * Opened by [DictationTileService]: starts the floating button and closes
 * straight away. Without the setup steps done it opens the app instead.
 */
class TileLaunchActivity : Activity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (BubblePermissions.hasOverlayPermission(this) && BubblePermissions.isAccessibilityServiceEnabled(this)) {
            ContextCompat.startForegroundService(this, Intent(this, BubbleService::class.java))
        } else {
            Toast.makeText(this, R.string.tile_setup_first, Toast.LENGTH_SHORT).show()
            startActivity(Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }
        finish()
    }
}
