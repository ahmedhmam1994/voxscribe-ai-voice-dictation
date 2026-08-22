package com.voxscribe.android

import android.content.Context
import android.content.Intent
import android.provider.Settings
import androidx.core.net.toUri

/**
 * The two permissions floating-bubble mode needs, neither of which has a
 * normal runtime-dialog path (unlike RECORD_AUDIO in PermissionActivity.kt):
 * both require sending the user into a system Settings screen by hand.
 * Used by SetupActivity's floating-bubble section (Phase 5) and can be
 * checked again at bubble-service start time to fail closed if either
 * permission was revoked after being granted once.
 */
object BubblePermissions {

    fun hasOverlayPermission(context: Context): Boolean = Settings.canDrawOverlays(context)

    fun overlayPermissionIntent(context: Context): Intent =
        Intent(
            Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
            "package:${context.packageName}".toUri(),
        )

    /**
     * Android has no per-service query API -- the enabled list is a single
     * colon-separated string of "package/ServiceClass" entries, so this
     * checks membership by substring on our own service's flattened name.
     */
    fun isAccessibilityServiceEnabled(context: Context): Boolean {
        val expected = "${context.packageName}/${VoxScribeAccessibilityService::class.java.name}"
        val enabled = Settings.Secure.getString(
            context.contentResolver,
            Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES,
        ) ?: return false
        return enabled.split(':').any { it.equals(expected, ignoreCase = true) }
    }

    /**
     * Android provides no reliable deep link straight to one service's
     * toggle across OEMs -- this opens the general Accessibility settings
     * list, same as Wispr Flow's own setup flow does, with an in-app label
     * (Phase 5) telling the user which entry ("VoxScribe") to tap.
     */
    fun accessibilitySettingsIntent(): Intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
}
