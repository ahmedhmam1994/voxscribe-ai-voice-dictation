package com.voxscribe.android

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import android.os.SystemClock
import androidx.core.content.ContextCompat
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel

/**
 * Lets the Flutter Dictation screen record and transcribe with the same
 * [DictationEngine] the floating button uses.
 *
 * Methods: `start` begins recording; `stop` ends it and answers with
 * `{text, durationMs}` once transcription finishes. Input levels (0 to 1)
 * stream over the events channel while recording.
 */
class EngineChannel(private val activity: Activity) :
    MethodChannel.MethodCallHandler, EventChannel.StreamHandler {

    private var engine: DictationEngine? = null
    private var levels: EventChannel.EventSink? = null
    private var pendingStop: MethodChannel.Result? = null
    private var failure: String? = null
    private var startedAt = 0L

    fun register(messenger: BinaryMessenger) {
        MethodChannel(messenger, METHOD_CHANNEL).setMethodCallHandler(this)
        EventChannel(messenger, LEVELS_CHANNEL).setStreamHandler(this)
    }

    override fun onListen(arguments: Any?, events: EventChannel.EventSink) {
        levels = events
    }

    override fun onCancel(arguments: Any?) {
        levels = null
    }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "start" -> start(result)
            "stop" -> stop(result)
            "getLanguage" -> result.success(SettingsStore.whisperLanguage(activity))
            "setLanguage" -> setLanguage(call.argument<String>("code").orEmpty(), result)
            else -> result.notImplemented()
        }
    }

    private fun start(result: MethodChannel.Result) {
        val granted = ContextCompat.checkSelfPermission(activity, Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED
        if (!granted) {
            result.error(ERROR_NO_MICROPHONE, "Allow the microphone in Setup first.", null)
            return
        }
        engine?.destroy()
        failure = null
        engine = DictationEngine(
            context = activity,
            onResult = ::finish,
            onFailure = ::fail,
            onLevel = { level -> levels?.success(level.toDouble()) },
        )
        startedAt = SystemClock.elapsedRealtime()
        engine?.startListening()
        // A recorder that cannot start reports through onFailure straight away.
        val startError = failure
        if (startError != null) {
            result.error(ERROR_FAILED, startError, null)
        } else {
            result.success(null)
        }
    }

    private fun stop(result: MethodChannel.Result) {
        val current = engine
        if (current == null) {
            result.error(ERROR_FAILED, "Nothing is recording.", null)
            return
        }
        failure?.let {
            result.error(ERROR_FAILED, it, null)
            return
        }
        pendingStop = result
        current.stopListening()
    }

    private fun setLanguage(code: String, result: MethodChannel.Result) {
        SettingsStore.setWhisperLanguage(activity, code)
        // Reloading the model takes a moment, so keep it off the main thread.
        Thread {
            WhisperEngine.reload(activity)
            activity.runOnUiThread { result.success(null) }
        }.start()
    }

    private fun finish(text: String) {
        val elapsed = SystemClock.elapsedRealtime() - startedAt
        pendingStop?.success(mapOf("text" to text, "durationMs" to elapsed))
        release()
    }

    private fun fail(message: String) {
        failure = message
        pendingStop?.error(ERROR_FAILED, message, null)
        if (pendingStop != null) release()
    }

    private fun release() {
        pendingStop = null
        engine?.destroy()
        engine = null
    }

    private companion object {
        const val METHOD_CHANNEL = "com.voxscribe.android/engine"
        const val LEVELS_CHANNEL = "com.voxscribe.android/engine/levels"
        const val ERROR_NO_MICROPHONE = "no_microphone"
        const val ERROR_FAILED = "failed"
    }
}
