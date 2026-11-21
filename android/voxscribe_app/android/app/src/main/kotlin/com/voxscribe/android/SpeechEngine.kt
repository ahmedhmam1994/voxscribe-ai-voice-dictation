package com.voxscribe.android

import android.content.Context
import android.util.Log

/**
 * Turns speech into text on the phone with one of two downloaded models,
 * chosen by the language the user speaks:
 *   - Granite ([GraniteModel]) for English, French, Spanish, German, Italian
 *     and Portuguese.
 *   - Nemotron ([ArabicModel]) for Arabic and Turkish.
 *
 * Nothing is bundled and there is no other recognizer to fall back on: until
 * the model for the chosen language is downloaded, dictation says so (see
 * [notReadyMessage]) instead of typing worse text.
 *
 * Loading takes a few seconds, so BubbleService warms it up on a background
 * thread; every public call that needs the model is synchronized, so a warm-up,
 * a dictation and a file import take turns.
 */
object SpeechEngine {
    private const val TAG = "SpeechEngine"

    /** Both models take 16 kHz mono audio. */
    const val SAMPLE_RATE = 16000

    /** The two downloadable models. [key] is the name the Flutter side uses. */
    enum class Model(val key: String) {
        GRANITE("english"),
        NEMOTRON("arabic");

        fun isInstalled(context: Context): Boolean = when (this) {
            GRANITE -> GraniteModel.isInstalled(context)
            NEMOTRON -> ArabicModel.isInstalled(context)
        }

        fun status(context: Context): Map<String, Any?> = when (this) {
            GRANITE -> GraniteModel.status(context)
            NEMOTRON -> ArabicModel.status(context)
        }

        companion object {
            fun fromKey(key: String?): Model? = entries.firstOrNull { it.key == key }
        }
    }

    /** The languages each model types, by the codes the language picker saves. */
    private val NEMOTRON_LANGUAGES = setOf("ar", "tr")
    val LANGUAGES = setOf("en", "fr", "es", "de", "it", "pt") + NEMOTRON_LANGUAGES

    fun modelFor(language: String): Model =
        if (language in NEMOTRON_LANGUAGES) Model.NEMOTRON else Model.GRANITE

    /** The model the chosen language needs. */
    fun neededModel(context: Context): Model = modelFor(SettingsStore.language(context))

    /** True when the model for the chosen language is on the phone. Cheap: checks file sizes only. */
    fun isInstalled(context: Context): Boolean = neededModel(context).isInstalled(context)

    private var granite: GraniteEngine? = null
    private var nemotron: ArabicEngine? = null
    private var checked = false
    private var loadError: Throwable? = null

    /** Loads the model for the chosen language if it is there. True when it is ready to transcribe. */
    @Synchronized
    fun isReady(context: Context): Boolean {
        ensureLoaded(context)
        return granite != null || nemotron != null
    }

    /**
     * What to tell someone who pressed the button before the model is ready:
     * still downloading (with the percentage), never downloaded, or failed to load.
     */
    fun notReadyMessage(context: Context): String {
        val status = neededModel(context).status(context)
        return when {
            status["downloading"] == true -> "Speech model downloading, ${status["percent"]}%"
            !isInstalled(context) -> "Download the speech model first"
            else -> "Speech model failed. Redownload in Settings"
        }
    }

    @Synchronized
    private fun ensureLoaded(context: Context) {
        if (checked) return
        checked = true
        val app = context.applicationContext
        val language = SettingsStore.language(app)
        val model = modelFor(language)
        if (!model.isInstalled(app)) {
            Log.i(TAG, "The ${model.key} model is not downloaded yet.")
            FirstRun.step(app, "model_failed", FirstRun.modelCode(null, filesPresent = false))
            return
        }
        val started = System.currentTimeMillis()
        try {
            when (model) {
                Model.GRANITE -> granite = GraniteEngine.load(app)
                Model.NEMOTRON -> nemotron = ArabicEngine.load(app, language)
            }
            val seconds = (System.currentTimeMillis() - started) / 1000.0
            Log.i(TAG, "${model.key} model ready in ${seconds}s.")
            FirstRun.step(app, "model_ready", once = true, extra = mapOf("load" to FirstRun.secondsBucket(seconds)))
        } catch (e: Throwable) {
            // A damaged file or a library problem (UnsatisfiedLinkError, out of
            // memory) lands here: report it, never crash the app.
            Log.e(TAG, "The ${model.key} model failed to load", e)
            loadError = e
            FirstRun.step(app, "model_failed", FirstRun.modelCode(e, filesPresent = true))
        }
    }

    /**
     * Loads again so a changed language or a finished download takes effect.
     * Blocking: call from a background thread.
     */
    @Synchronized
    fun reload(context: Context) {
        granite?.release()
        granite = null
        nemotron?.release()
        nemotron = null
        loadError = null
        checked = false
        ensureLoaded(context)
    }

    /**
     * The words in [samples], or null when no model is ready (see
     * [notReadyMessage]). Blocking and CPU bound: never call it on the main thread.
     */
    @Synchronized
    fun transcribe(context: Context, samples: FloatArray): String? {
        ensureLoaded(context)
        granite?.let { return it.transcribe(samples) }
        nemotron?.let { return it.transcribe(samples) }
        return null
    }

    /** One line for Settings > Copy diagnostics. */
    @Synchronized
    fun diagnostics(context: Context): String {
        val model = neededModel(context)
        val state = when {
            granite != null || nemotron != null -> "loaded"
            loadError != null -> "failed (${FirstRun.modelCode(loadError, filesPresent = true)})"
            !model.isInstalled(context) -> "not downloaded"
            else -> "not loaded yet"
        }
        return "Speech model: ${model.key} for ${SettingsStore.language(context)}, $state"
    }
}
