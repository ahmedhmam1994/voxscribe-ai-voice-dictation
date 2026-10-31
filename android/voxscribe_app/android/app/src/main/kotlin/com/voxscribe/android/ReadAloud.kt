package com.voxscribe.android

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.speech.tts.TextToSpeech
import android.widget.Toast

/**
 * Read it back: the phone's own text-to-speech voice reads a dictation aloud,
 * so it can be checked without looking. Only a voice that works offline is
 * used, so the text never leaves the phone; without one it says how to get
 * one. One shared engine, created on first use and kept for the process.
 */
object ReadAloud {
    private val main = Handler(Looper.getMainLooper())
    private var tts: TextToSpeech? = null
    private var ready = false
    private var offline = false
    private var appContext: Context? = null
    private var pending: String? = null

    /** Reads [text] aloud, cutting off anything still being read. */
    fun speak(context: Context, text: String) {
        if (text.isBlank()) return
        main.post {
            appContext = context.applicationContext
            val engine = tts
            when {
                engine == null -> {
                    pending = text
                    tts = TextToSpeech(context.applicationContext) { status -> main.post { onReady(status) } }
                }
                ready -> say(engine, text)
                else -> pending = text
            }
        }
    }

    fun stop() {
        main.post {
            pending = null
            tts?.stop()
        }
    }

    fun isSpeaking(): Boolean = tts?.isSpeaking == true

    private fun onReady(status: Int) {
        val engine = tts ?: return
        if (status != TextToSpeech.SUCCESS) {
            engine.shutdown()
            tts = null
            pending = null
            return
        }
        ready = true
        offline = useOfflineVoice(engine)
        pending?.let { say(engine, it) }
        pending = null
    }

    /** Swaps a voice that needs the internet for an offline one in the same language. False when there is none. */
    private fun useOfflineVoice(engine: TextToSpeech): Boolean = runCatching {
        val current = engine.voice ?: engine.defaultVoice ?: return@runCatching false
        if (!current.isNetworkConnectionRequired) return@runCatching true
        val offline = engine.voices.orEmpty()
            .filter { !it.isNetworkConnectionRequired && it.locale.language == current.locale.language }
            .maxByOrNull { it.quality } ?: return@runCatching false
        engine.voice = offline
        true
    }.getOrDefault(false)

    private fun say(engine: TextToSpeech, text: String) {
        // Looks again each time, in case a voice was downloaded since.
        if (!offline) offline = useOfflineVoice(engine)
        if (!offline) {
            appContext?.let { Toast.makeText(it, R.string.read_back_no_offline_voice, Toast.LENGTH_LONG).show() }
            return
        }
        engine.speak(text.take(TextToSpeech.getMaxSpeechInputLength()), TextToSpeech.QUEUE_FLUSH, null, "voxscribe-read-back")
    }
}
