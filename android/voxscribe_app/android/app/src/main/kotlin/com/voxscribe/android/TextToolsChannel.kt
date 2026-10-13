package com.voxscribe.android

import android.content.Context
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel

/** Lets the Flutter text tools screen read and change the saved text tool settings. */
class TextToolsChannel(private val context: Context) : MethodChannel.MethodCallHandler {

    fun register(messenger: BinaryMessenger) {
        MethodChannel(messenger, CHANNEL_NAME).setMethodCallHandler(this)
    }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "getTextTools" -> {
                val saved = TextToolsStore.snapshot(context)
                result.success(
                    mapOf(
                        "voiceCommands" to saved.voiceCommands,
                        "smartFormat" to saved.smartFormat,
                        "codeDictation" to saved.codeDictation,
                        "replacements" to saved.replacements,
                        "templates" to saved.templates,
                        "profiles" to saved.profiles,
                    ),
                )
            }
            "setTextTools" -> {
                TextToolsStore.save(
                    context,
                    TextToolsStore.Snapshot(
                        voiceCommands = call.argument<Boolean>("voiceCommands") == true,
                        smartFormat = call.argument<Boolean>("smartFormat") == true,
                        codeDictation = call.argument<Boolean>("codeDictation") == true,
                        replacements = call.argument<String>("replacements").orEmpty(),
                        templates = call.argument<String>("templates").orEmpty(),
                        profiles = call.argument<String>("profiles").orEmpty(),
                    ),
                )
                result.success(null)
            }
            else -> result.notImplemented()
        }
    }

    private companion object {
        const val CHANNEL_NAME = "com.voxscribe.android/texttools"
    }
}
