package com.voxscribe.android

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.core.app.ActivityCompat

/**
 * A Service (which is what [VoxScribeInputMethodService] is) cannot pop the
 * runtime permission dialog itself, so the IME launches this transparent,
 * throwaway activity to ask for RECORD_AUDIO, then it finishes immediately.
 */
class PermissionActivity : Activity() {

    private val requestCode = 1001

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.RECORD_AUDIO), requestCode)
        } else {
            finish()
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        // Switch back to whatever app/field the user was in; they'll need to
        // reopen the VoxScribe keyboard once (Android doesn't let us restore
        // IME view state across a permission prompt automatically).
        finish()
    }
}
