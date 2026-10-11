package com.voxscribe.android

import android.content.Context
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel

/** Lets the Flutter screens read, add to and clear the dictation history. */
class HistoryChannel(private val context: Context) : MethodChannel.MethodCallHandler {

    fun register(messenger: BinaryMessenger) {
        MethodChannel(messenger, CHANNEL_NAME).setMethodCallHandler(this)
    }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "getEntries" -> result.success(HistoryStore.all(context).map(::toMap))
            "addEntry" -> {
                val text = call.argument<String>("text").orEmpty()
                val at = call.argument<Number>("at")?.toLong() ?: System.currentTimeMillis()
                val ms = call.argument<Number>("ms")?.toLong() ?: 0L
                if (text.isNotBlank()) HistoryStore.add(context, HistoryEntry(text, at, ms))
                result.success(null)
            }
            "clear" -> {
                HistoryStore.clear(context)
                result.success(null)
            }
            else -> result.notImplemented()
        }
    }

    private fun toMap(entry: HistoryEntry) = mapOf(
        "text" to entry.text,
        "at" to entry.atMillis,
        "ms" to entry.durationMillis,
    )

    private companion object {
        const val CHANNEL_NAME = "com.voxscribe.android/history"
    }
}
