package com.voxscribe.android

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel

/**
 * Lets the Flutter setup screen read permission state and trigger the system
 * screens and services the floating button depends on.
 */
class SetupChannel(private val activity: Activity) : MethodChannel.MethodCallHandler {

    fun register(messenger: BinaryMessenger) {
        MethodChannel(messenger, CHANNEL_NAME).setMethodCallHandler(this)
    }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "getStatus" -> result.success(status())
            "requestMicrophone" -> {
                requestMicrophone()
                result.success(null)
            }
            "openAccessibilitySettings" -> {
                activity.startActivity(BubblePermissions.accessibilitySettingsIntent())
                result.success(null)
            }
            "openOverlaySettings" -> {
                activity.startActivity(BubblePermissions.overlayPermissionIntent(activity))
                result.success(null)
            }
            "setBubbleRunning" -> setBubbleRunning(call.argument<Boolean>("running") == true, result)
            else -> result.notImplemented()
        }
    }

    private fun status(): Map<String, Boolean> = mapOf(
        "microphone" to hasMicrophone(),
        "accessibility" to BubblePermissions.isAccessibilityServiceEnabled(activity),
        // Android can leave the service switched on but disconnected after an app update.
        "accessibilityConnected" to (VoxScribeAccessibilityService.instance != null),
        "overlay" to BubblePermissions.hasOverlayPermission(activity),
        "bubbleRunning" to BubbleService.isRunning,
    )

    private fun hasMicrophone(): Boolean =
        ContextCompat.checkSelfPermission(activity, Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED

    private fun requestMicrophone() {
        val permissions = mutableListOf(Manifest.permission.RECORD_AUDIO)
        // Android 13+: lets the floating button's notification show.
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissions += Manifest.permission.POST_NOTIFICATIONS
        }
        ActivityCompat.requestPermissions(activity, permissions.toTypedArray(), REQUEST_CODE)
    }

    private fun setBubbleRunning(running: Boolean, result: MethodChannel.Result) {
        val intent = Intent(activity, BubbleService::class.java)
        if (!running) {
            activity.stopService(intent)
            result.success(null)
            return
        }
        if (!BubblePermissions.hasOverlayPermission(activity) ||
            !BubblePermissions.isAccessibilityServiceEnabled(activity)
        ) {
            result.error("permissions_missing", "Finish the setup steps first.", null)
            return
        }
        ContextCompat.startForegroundService(activity, intent)
        result.success(null)
    }

    private companion object {
        const val CHANNEL_NAME = "com.voxscribe.android/setup"
        const val REQUEST_CODE = 1002
    }
}
