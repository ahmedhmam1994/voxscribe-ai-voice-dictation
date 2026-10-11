package com.voxscribe.android

import android.content.Context
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel

/** Lets the Flutter settings screen read and change the app's saved settings. */
class SettingsChannel(private val context: Context) : MethodChannel.MethodCallHandler {

    fun register(messenger: BinaryMessenger) {
        MethodChannel(messenger, CHANNEL_NAME).setMethodCallHandler(this)
    }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "getSettings" -> result.success(
                mapOf(
                    "cleanup" to SettingsStore.cleanupEnabled(context),
                    "trailingSpace" to SettingsStore.trailingSpaceEnabled(context),
                    "theme" to SettingsStore.themeMode(context),
                ),
            )
            "setCleanup" -> {
                SettingsStore.setCleanupEnabled(context, call.argument<Boolean>("value") == true)
                result.success(null)
            }
            "setTrailingSpace" -> {
                SettingsStore.setTrailingSpaceEnabled(context, call.argument<Boolean>("value") == true)
                result.success(null)
            }
            "setTheme" -> {
                SettingsStore.setThemeMode(context, call.argument<String>("value").orEmpty())
                result.success(null)
            }
            else -> result.notImplemented()
        }
    }

    private companion object {
        const val CHANNEL_NAME = "com.voxscribe.android/settings"
    }
}
