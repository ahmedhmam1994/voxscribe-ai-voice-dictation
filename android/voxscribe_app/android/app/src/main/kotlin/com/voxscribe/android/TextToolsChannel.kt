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
                        "sendIt" to saved.sendIt,
                        "mode" to saved.mode,
                        "autoModes" to saved.autoModes,
                        "termPacks" to saved.termPacks,
                        "spokenFormats" to saved.spokenFormats,
                        "readBack" to saved.readBack,
                        "formFill" to saved.formFill,
                        "formFillsLeft" to FormFillTries.left(context),
                        "screenSpelling" to saved.screenSpelling,
                        "learnFixes" to saved.learnFixes,
                        "learned" to LearnedWords.text(context),
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
                        sendIt = call.argument<Boolean>("sendIt") == true,
                        mode = call.argument<String>("mode") ?: Modes.DEFAULT,
                        autoModes = call.argument<Boolean>("autoModes") != false,
                        termPacks = call.argument<String>("termPacks").orEmpty(),
                        spokenFormats = call.argument<Boolean>("spokenFormats") == true,
                        readBack = call.argument<Boolean>("readBack") == true,
                        formFill = call.argument<Boolean>("formFill") != false,
                        screenSpelling = call.argument<Boolean>("screenSpelling") != false,
                        learnFixes = call.argument<Boolean>("learnFixes") != false,
                    ),
                )
                result.success(null)
            }
            "addLearned" -> {
                // Fixes learned on another device, kept with the same rules.
                Replacements.parse(call.argument<String>("lines").orEmpty()).forEach { (heard, fixed) ->
                    if (heard.isNotBlank() && fixed.isNotBlank()) {
                        LearnedWords.remember(context, LearnedWords.Fix(heard, fixed))
                    }
                }
                result.success(LearnedWords.text(context))
            }
            "forgetLearned" -> {
                LearnedWords.forget(context, call.argument<String>("heard").orEmpty())
                result.success(LearnedWords.text(context))
            }
            else -> result.notImplemented()
        }
    }

    private companion object {
        const val CHANNEL_NAME = "com.voxscribe.android/texttools"
    }
}
