package com.voxscribe.android

import android.content.Context
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel

/** The privacy receipt for the Flutter screens (see [NetworkLog]), and the update check's own entries. */
class NetworkLogChannel(private val context: Context) : MethodChannel.MethodCallHandler {

    fun register(messenger: BinaryMessenger) {
        MethodChannel(messenger, CHANNEL_NAME).setMethodCallHandler(this)
    }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "entries" -> result.success(
                NetworkLog.entries(context).map {
                    mapOf("at" to it.atMillis, "what" to it.what, "host" to it.host, "sent" to it.sent)
                },
            )
            "record" -> {
                NetworkLog.record(
                    context,
                    what = call.argument<String>("what").orEmpty(),
                    url = call.argument<String>("url").orEmpty(),
                    sent = call.argument<String>("sent").orEmpty(),
                )
                result.success(null)
            }
            else -> result.notImplemented()
        }
    }

    private companion object {
        const val CHANNEL_NAME = "com.voxscribe.android/networklog"
    }
}
