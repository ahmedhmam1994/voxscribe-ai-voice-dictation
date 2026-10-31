package com.voxscribe.android

import android.content.Context
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel

/**
 * Lets the Flutter screens list, import and remove term packs, and run the
 * Teach your voice comparison. Which packs are on is saved with the text tools.
 */
class TermPacksChannel(private val context: Context) : MethodChannel.MethodCallHandler {

    fun register(messenger: BinaryMessenger) {
        MethodChannel(messenger, CHANNEL_NAME).setMethodCallHandler(this)
    }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "listPacks" -> result.success(TermPackStore.available(context).map(::infoMap))
            "importPack" -> {
                try {
                    val info = TermPackStore.import(
                        context,
                        call.argument<String>("fileName").orEmpty(),
                        call.argument<String>("text").orEmpty(),
                    )
                    result.success(infoMap(info))
                } catch (e: IllegalArgumentException) {
                    result.error(ERROR_INVALID, e.message, null)
                }
            }
            "removePack" -> result.success(TermPackStore.remove(context, call.argument<String>("id").orEmpty()))
            "teachScript" -> {
                val enabled = TermPackStore.enabled(TextToolsStore.snapshot(context))
                result.success(
                    VoiceTeach.buildScript(enabled).map { mapOf("sentence" to it.sentence, "terms" to it.terms) },
                )
            }
            "teachProposals" -> result.success(teachProposals(call.argument<List<Map<String, Any?>>>("readings").orEmpty()))
            else -> result.notImplemented()
        }
    }

    /** What each reading got wrong, merged into one list to tick. */
    private fun teachProposals(readings: List<Map<String, Any?>>): List<Map<String, Any>> {
        val enabled = TermPackStore.enabled(TextToolsStore.snapshot(context))
        val known = TermPacks.combinedTerms(
            TermPackStore.packs(context, enabled.ifEmpty { TermPacks.BUILTIN.map { it.first } }),
        )
        val slips = readings.map { reading ->
            @Suppress("UNCHECKED_CAST")
            val terms = (reading["terms"] as? List<String>).orEmpty()
            VoiceTeach.findSlips(
                reading["sentence"] as? String ?: "",
                terms,
                reading["heard"] as? String ?: "",
                known,
            )
        }
        return VoiceTeach.merge(slips).map { mapOf("heard" to it.heard, "expected" to it.expected, "count" to it.count) }
    }

    private fun infoMap(info: TermPackStore.Info): Map<String, Any> =
        mapOf("id" to info.id, "label" to info.label, "count" to info.count, "user" to info.user)

    private companion object {
        const val CHANNEL_NAME = "com.voxscribe.android/termpacks"
        const val ERROR_INVALID = "invalid"
    }
}
