package com.voxscribe.android

import android.app.Activity
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel

/**
 * Settings talks to the optional English fast model through this: `status`,
 * `download`, `cancel`, `delete` and `select` (true for the fast model, false
 * for the bundled Whisper).
 */
class FastModelChannel(private val activity: Activity) : MethodChannel.MethodCallHandler {

    fun register(messenger: BinaryMessenger) {
        MethodChannel(messenger, CHANNEL).setMethodCallHandler(this)
    }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "status" -> result.success(FastModel.status(activity))
            "download" -> {
                FastModel.download(activity)
                result.success(null)
            }
            "cancel" -> {
                FastModel.cancel()
                result.success(null)
            }
            "delete" -> {
                reload { FastModel.delete(activity) }
                result.success(null)
            }
            "select" -> {
                val fast = call.argument<Boolean>("fast") == true
                if (fast && !FastModel.isInstalled(activity)) {
                    result.error("not_installed", "Download the model first.", null)
                } else {
                    SettingsStore.setSpeechModel(activity, if (fast) SettingsStore.MODEL_FAST else SettingsStore.MODEL_BASE)
                    // Loading the other model takes a few seconds, so keep it off the main thread.
                    Thread {
                        WhisperEngine.reload(activity)
                        activity.runOnUiThread { result.success(null) }
                    }.start()
                }
            }
            else -> result.notImplemented()
        }
    }

    private fun reload(change: () -> Unit) {
        change()
        Thread { WhisperEngine.reload(activity) }.start()
    }

    private companion object {
        const val CHANNEL = "com.voxscribe.android/fastmodel"
    }
}
