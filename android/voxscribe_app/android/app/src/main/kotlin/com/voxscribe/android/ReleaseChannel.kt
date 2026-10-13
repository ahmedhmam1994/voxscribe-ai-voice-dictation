package com.voxscribe.android

import android.content.Context
import android.content.Intent
import android.net.Uri
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel

/**
 * Lets the Flutter side know which version is installed, remember which
 * version's "what's new" was shown and which update was dismissed, and open a
 * download link in the browser.
 */
class ReleaseChannel(private val context: Context) : MethodChannel.MethodCallHandler {

    fun register(messenger: BinaryMessenger) {
        MethodChannel(messenger, CHANNEL_NAME).setMethodCallHandler(this)
    }

    private val prefs get() = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "getState" -> {
                val version = context.packageManager
                    .getPackageInfo(context.packageName, 0).versionName.orEmpty()
                result.success(
                    mapOf(
                        "version" to version,
                        "lastSeen" to prefs.getString(KEY_LAST_SEEN, null),
                        "dismissedUpdate" to prefs.getString(KEY_DISMISSED, null),
                    ),
                )
            }
            "markSeen" -> {
                prefs.edit().putString(KEY_LAST_SEEN, call.argument<String>("version")).apply()
                result.success(null)
            }
            "dismissUpdate" -> {
                prefs.edit().putString(KEY_DISMISSED, call.argument<String>("version")).apply()
                result.success(null)
            }
            "openUrl" -> {
                val url = call.argument<String>("url").orEmpty()
                // Only the project's own GitHub pages, never an arbitrary link.
                if (!url.startsWith("https://github.com/")) {
                    result.success(false)
                    return
                }
                val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                result.success(runCatching { context.startActivity(intent) }.isSuccess)
            }
            else -> result.notImplemented()
        }
    }

    private companion object {
        const val CHANNEL_NAME = "com.voxscribe.android/release"
        const val PREFS = "voxscribe_release"
        const val KEY_LAST_SEEN = "last_seen_version"
        const val KEY_DISMISSED = "dismissed_update"
    }
}
