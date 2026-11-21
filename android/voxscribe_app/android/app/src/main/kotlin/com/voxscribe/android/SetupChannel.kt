package com.voxscribe.android

import android.Manifest
import android.app.Activity
import android.app.StatusBarManager
import android.content.ComponentName
import android.content.Intent
import android.graphics.drawable.Icon
import android.content.pm.PackageManager
import android.os.Build
import android.os.Looper
import android.os.Handler
import android.provider.Settings
import androidx.core.app.ActivityCompat
import androidx.core.app.NotificationManagerCompat
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
            "getStatus" -> {
                val status = status()
                Telemetry.sendSetupProgress(activity, doneSteps(status))
                result.success(status)
            }
            "setupOpened" -> {
                Telemetry.sendSetupOpened(activity)
                SettingsStore.setSetupSeen(activity)
                result.success(null)
            }
            "requestMicrophone" -> {
                requestMicrophone()
                result.success(null)
            }
            "openAccessibilitySettings" -> {
                activity.startActivity(BubblePermissions.accessibilitySettingsIntent())
                result.success(null)
            }
            "openAppInfo" -> {
                activity.startActivity(BubblePermissions.appInfoIntent(activity))
                result.success(null)
            }
            "openOverlaySettings" -> {
                activity.startActivity(BubblePermissions.overlayPermissionIntent(activity))
                result.success(null)
            }
            "openNotificationSettings" -> {
                activity.startActivity(
                    Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                        .putExtra(Settings.EXTRA_APP_PACKAGE, activity.packageName),
                )
                result.success(null)
            }
            "requestBatteryExemption" -> {
                requestBatteryExemption()
                result.success(null)
            }
            "addQuickTile" -> addQuickTile(result)
            "setBubbleRunning" -> setBubbleRunning(call.argument<Boolean>("running") == true, result)
            "downloadModel" -> {
                when (SpeechEngine.neededModel(activity)) {
                    SpeechEngine.Model.GRANITE -> GraniteModel.download(activity)
                    SpeechEngine.Model.NEMOTRON -> ArabicModel.download(activity)
                }
                result.success(null)
            }
            "cancelModel" -> {
                when (SpeechEngine.neededModel(activity)) {
                    SpeechEngine.Model.GRANITE -> GraniteModel.cancel()
                    SpeechEngine.Model.NEMOTRON -> ArabicModel.cancel()
                }
                result.success(null)
            }
            "setLanguage" -> {
                val code = call.argument<String>("code").orEmpty()
                if (code !in SpeechEngine.LANGUAGES) return result.error("bad_language", "That language is not supported.", null)
                SettingsStore.setLanguage(activity, code)
                // Loading the other model takes a moment, so keep it off the main thread.
                Thread {
                    SpeechEngine.reload(activity)
                    activity.runOnUiThread { result.success(null) }
                }.start()
            }
            else -> result.notImplemented()
        }
    }

    private fun status(): Map<String, Any?> {
        // The speech model the chosen language needs: downloaded, downloading, or not yet.
        val model = SpeechEngine.neededModel(activity).status(activity)
        return mapOf(
            "microphone" to hasMicrophone(),
            "accessibility" to BubblePermissions.isAccessibilityServiceEnabled(activity),
            // Android can leave the service switched on but disconnected after an app update.
            "accessibilityConnected" to (VoxScribeAccessibilityService.instance != null),
            // Installed from a file on Android 13+: the switch is greyed out until allowed in App info.
            "accessibilityRestricted" to BubblePermissions.mayBeRestricted(activity),
            "overlay" to BubblePermissions.hasOverlayPermission(activity),
            "bubbleRunning" to BubbleService.isRunning,
            // Off by default on Android 13 and newer until the user allows it.
            "notifications" to NotificationManagerCompat.from(activity).areNotificationsEnabled(),
            // Battery saving can stop the floating button; this says it is exempt.
            "batteryUnrestricted" to isBatteryUnrestricted(),
            // Xiaomi phones have their own battery saver on top of Android's.
            "xiaomi" to isXiaomi(),
            // A new install starts on the setup steps until it has opened them once.
            "setupSeen" to SettingsStore.setupSeen(activity),
            // Until the floating button is pressed once, the app offers a practice box.
            "bubbleUsed" to SettingsStore.bubbleUsed(activity),
            "language" to SettingsStore.language(activity),
            "modelInstalled" to model["installed"],
            "modelDownloading" to model["downloading"],
            "modelPercent" to model["percent"],
            "modelMegabytes" to model["megabytes"],
            "modelError" to model["error"],
        )
    }

    /** The setup pings (see [Telemetry.SETUP_EVENTS]) whose step is done in [status]. */
    private fun doneSteps(status: Map<String, Any?>): Set<String> = buildSet {
        if (status["microphone"] == true) add("setup_microphone")
        if (status["accessibility"] == true && status["accessibilityConnected"] == true) {
            add("setup_accessibility")
        }
        if (status["overlay"] == true) add("setup_overlay")
        if (status["bubbleRunning"] == true) add("bubble_started")
    }

    private fun isBatteryUnrestricted(): Boolean {
        val power = activity.getSystemService(android.os.PowerManager::class.java) ?: return true
        return power.isIgnoringBatteryOptimizations(activity.packageName)
    }

    private fun isXiaomi(): Boolean =
        Build.MANUFACTURER.lowercase() in setOf("xiaomi", "redmi", "poco")

    /** Android's own one-tap "Allow" dialog, or the battery list where that dialog is missing. */
    @android.annotation.SuppressLint("BatteryLife") // The floating button is a tool the user starts on purpose.
    private fun requestBatteryExemption() {
        val ask = Intent(
            Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
            android.net.Uri.parse("package:${activity.packageName}"),
        )
        val opened = runCatching { activity.startActivity(ask) }.isSuccess
        if (!opened) runCatching { activity.startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)) }
    }

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

    /** Android 13+ shows its own "Add tile" prompt; older versions need the user to add it by hand. */
    /**
     * Asks Android to add the tile and answers "added", "already", "declined" or
     * "manual" (the user has to add it by hand). Some phones (MIUI) take the
     * request and show nothing, so when no prompt took the screen within a
     * moment the answer is "manual".
     */
    private fun addQuickTile(result: MethodChannel.Result) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return result.success("manual")
        val manager = activity.getSystemService(StatusBarManager::class.java) ?: return result.success("manual")
        val main = Handler(Looper.getMainLooper())
        var answered = false
        fun answer(value: String) {
            if (answered) return
            answered = true
            result.success(value)
        }
        val asked = runCatching {
            manager.requestAddTileService(
                ComponentName(activity, DictationTileService::class.java),
                activity.getString(R.string.tile_label),
                Icon.createWithResource(activity, R.drawable.ic_tile_mic),
                ContextCompat.getMainExecutor(activity),
            ) { code ->
                main.post {
                    answer(
                        when (code) {
                            StatusBarManager.TILE_ADD_REQUEST_RESULT_TILE_ADDED -> "added"
                            StatusBarManager.TILE_ADD_REQUEST_RESULT_TILE_ALREADY_ADDED -> "already"
                            StatusBarManager.TILE_ADD_REQUEST_RESULT_TILE_NOT_ADDED -> "declined"
                            else -> "manual"
                        },
                    )
                }
            }
        }.isSuccess
        if (!asked) return answer("manual")
        // A shown prompt takes the focus; still focused means nothing was shown.
        main.postDelayed({ if (activity.hasWindowFocus()) answer("manual") }, 1500)
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
