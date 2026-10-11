package com.voxscribe.android

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Handler
import android.os.Looper
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel

/** Lets the Flutter screens unlock Pro and edit snippets. */
class ProChannel(private val context: Context) : MethodChannel.MethodCallHandler {
    private val mainHandler = Handler(Looper.getMainLooper())

    fun register(messenger: BinaryMessenger) {
        MethodChannel(messenger, CHANNEL_NAME).setMethodCallHandler(this)
    }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "isPro" -> result.success(LicenseStore.isPro(context))
            "activate" -> activate(call.argument<String>("key").orEmpty(), result)
            "deactivate" -> {
                LicenseStore.clear(context)
                result.success(null)
            }
            "openPurchasePage" -> {
                context.startActivity(
                    Intent(Intent.ACTION_VIEW, Uri.parse(PURCHASE_URL)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                )
                result.success(null)
            }
            "getSnippets" -> result.success(
                SnippetStore.all(context).map { mapOf("trigger" to it.trigger, "expansion" to it.expansion) },
            )
            "setSnippets" -> {
                val items = call.argument<List<Map<String, String>>>("snippets").orEmpty()
                SnippetStore.replaceAll(
                    context,
                    items.map { Snippet(it["trigger"].orEmpty(), it["expansion"].orEmpty()) },
                )
                result.success(null)
            }
            else -> result.notImplemented()
        }
    }

    private fun activate(key: String, result: MethodChannel.Result) {
        if (!LicenseKey.isValid(key)) {
            result.success(mapOf("ok" to false, "message" to "That key is not valid. Check for typos."))
            return
        }
        Thread {
            val outcome = ActivationClient.activate(context, key)
            if (outcome.ok) LicenseStore.save(context, key)
            mainHandler.post { result.success(mapOf("ok" to outcome.ok, "message" to outcome.message)) }
        }.start()
    }

    private companion object {
        const val CHANNEL_NAME = "com.voxscribe.android/pro"
        const val PURCHASE_URL = "https://hmamster3.gumroad.com/l/tbsfom"
    }
}
