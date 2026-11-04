package com.voxscribe.android

import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.os.Build
import android.provider.Settings
import androidx.core.net.toUri

/**
 * The two permissions floating-bubble mode needs, neither of which has a
 * normal runtime-dialog path (unlike RECORD_AUDIO in PermissionActivity.kt):
 * both require sending the user into a system Settings screen by hand.
 * Used by the app's setup screen and can be
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
     * list, so the setup screen tells the user which entry ("VoxScribe") to tap.
     */
    fun accessibilitySettingsIntent(): Intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)

    fun appInfoIntent(context: Context): Intent =
        Intent(
            Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
            "package:${context.packageName}".toUri(),
        )

    /**
     * Android 13+ greys out the accessibility switch ("Restricted setting")
     * for apps installed from a downloaded or local file, until the user
     * allows it in App info. Whether it is still blocked is not readable by
     * an app (the app op needs a system permission), so this only says the
     * block can apply.
     */
    fun mayBeRestricted(context: Context): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return false
        val source = runCatching {
            context.packageManager.getInstallSourceInfo(context.packageName).packageSource
        }.getOrNull()
        return source == PackageInstaller.PACKAGE_SOURCE_DOWNLOADED_FILE ||
            source == PackageInstaller.PACKAGE_SOURCE_LOCAL_FILE
    }
}
