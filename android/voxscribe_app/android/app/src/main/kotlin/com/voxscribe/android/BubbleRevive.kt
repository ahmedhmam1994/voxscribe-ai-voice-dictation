package com.voxscribe.android

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.SystemClock
import android.util.Log
import androidx.core.content.ContextCompat

/**
 * Brings the floating button back after Android stopped it (battery saving,
 * low memory, an app update), as long as the user had it on and never turned
 * it off. Android keeps the accessibility service bound, so that service calls
 * this when it connects and as the user moves between apps.
 */
object BubbleRevive {

    private const val TAG = "VoxRevive"
    private const val RETRY_MS = 30_000L
    private const val RETURN_WINDOW_MS = 10 * 60_000L
    private var lastTry = 0L

    /** Whether the button should be started again: wanted, not running, and every permission still there. */
    fun shouldRevive(
        wanted: Boolean,
        running: Boolean,
        overlay: Boolean,
        accessibility: Boolean,
        microphone: Boolean,
    ): Boolean = wanted && !running && overlay && accessibility && microphone

    fun ifWanted(context: Context) {
        val now = SystemClock.elapsedRealtime()
        if (lastTry != 0L && now - lastTry < RETRY_MS) return
        val app = context.applicationContext
        val revive = shouldRevive(
            wanted = SettingsStore.bubbleWanted(app),
            running = BubbleService.isRunning,
            overlay = BubblePermissions.hasOverlayPermission(app),
            accessibility = BubblePermissions.isAccessibilityServiceEnabled(app),
            microphone = ContextCompat.checkSelfPermission(app, Manifest.permission.RECORD_AUDIO) ==
                PackageManager.PERMISSION_GRANTED,
        )
        if (!revive) return
        lastTry = now
        runCatching { ContextCompat.startForegroundService(app, Intent(app, BubbleService::class.java)) }
            .onSuccess { Log.i(TAG, "Floating button started again") }
            .onFailure { Log.w(TAG, "Android refused to start the floating button again", it) }
    }

    /** True when setup sent the user to the accessibility switch a moment ago. */
    fun returnDue(askedAt: Long, now: Long): Boolean = askedAt > 0L && now - askedAt in 0..RETURN_WINDOW_MS

    /** Brings VoxScribe's setup screen back to the front, so nobody is left in Settings wondering what next. */
    fun openApp(context: Context) {
        runCatching {
            context.startActivity(
                Intent(context, MainActivity::class.java)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP),
            )
        }.onFailure { Log.w(TAG, "Could not bring VoxScribe back to the front", it) }
    }
}
