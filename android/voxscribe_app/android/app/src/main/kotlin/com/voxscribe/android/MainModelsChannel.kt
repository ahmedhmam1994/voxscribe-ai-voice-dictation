package com.voxscribe.android

import android.app.Activity
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel

/**
 * The app talks to the two downloadable speech models through this:
 * `status`, `download`, `cancel` and `delete`, each with a `model` argument of
 * "english" (Granite) or "arabic" (Nemotron), and `needed`, which answers
 * which of them the chosen language uses. There is no switch: a model that is
 * there is used for its languages (see [SpeechEngine]).
 */
class MainModelsChannel(private val activity: Activity) : MethodChannel.MethodCallHandler {

    fun register(messenger: BinaryMessenger) {
        MethodChannel(messenger, CHANNEL).setMethodCallHandler(this)
    }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        if (call.method == "needed") {
            val model = SpeechEngine.neededModel(activity)
            return result.success(model.status(activity) + mapOf("model" to model.key))
        }
        val model = SpeechEngine.Model.fromKey(call.argument<String>("model"))
            ?: return result.error("bad_model", "Unknown model.", null)
        when (call.method) {
            "status" -> result.success(model.status(activity))
            "download" -> {
                when (model) {
                    SpeechEngine.Model.GRANITE -> GraniteModel.download(activity)
                    SpeechEngine.Model.NEMOTRON -> ArabicModel.download(activity)
                }
                result.success(null)
            }
            "cancel" -> {
                when (model) {
                    SpeechEngine.Model.GRANITE -> GraniteModel.cancel()
                    SpeechEngine.Model.NEMOTRON -> ArabicModel.cancel()
                }
                result.success(null)
            }
            "delete" -> {
                when (model) {
                    SpeechEngine.Model.GRANITE -> GraniteModel.delete(activity)
                    SpeechEngine.Model.NEMOTRON -> ArabicModel.delete(activity)
                }
                result.success(null)
            }
            else -> result.notImplemented()
        }
    }

    private companion object {
        const val CHANNEL = "com.voxscribe.android/mainmodels"
    }
}
