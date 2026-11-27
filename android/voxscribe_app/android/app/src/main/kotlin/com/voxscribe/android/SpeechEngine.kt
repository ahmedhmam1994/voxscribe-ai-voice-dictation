package com.voxscribe.android

import android.content.Context
import android.util.Log

/**
 * Turns speech into text on the phone with one of two downloaded models,
 * chosen by the language the user speaks:
 *   - Granite ([GraniteModel]) for English, French, Spanish, German, Italian
 *     and Portuguese.
 *   - Nemotron ([ArabicModel]) for Arabic, Turkish and the other languages in
 *     [NEMOTRON_LANGUAGES], each checked on synthetic speech before it was added
 *     (21 Nov 2026; Swedish, Danish, Norwegian, Romanian, Bulgarian, Croatian
 *     and Estonian were left out, at 18 to 67% word errors).
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
    private val NEMOTRON_LANGUAGES = setOf(
        "ar", "tr", "nl", "ru", "uk", "hi", "ja", "ko", "zh", "vi", "pl", "cs", "sk", "fi", "hu",
    )
    val LANGUAGES = setOf("en", "fr", "es", "de", "it", "pt") + NEMOTRON_LANGUAGES

    /** Japanese and Chinese are written without spaces between words. */
    fun writesWithoutSpaces(language: String): Boolean = language == "ja" || language == "zh"

    /**
     * Chinese and Japanese punctuation for [language]: Nemotron writes "，" as
     * ", " and "？" as "?" in Chinese (21 Nov 2026). Turns English marks next
     * to Chinese or Japanese characters into full width ones and drops the
     * spaces between those characters. Other languages are returned as they are.
     */
    fun cjkPunctuation(text: String, language: String): String {
        if (!writesWithoutSpaces(language)) return text
        val comma = if (language == "ja") "、" else "，"
        // A mark with a Chinese or Japanese character on either side.
        var out = Regex("(?<=$CJK)\\s*([,?!:;])\\s*|\\s*([,?!:;])\\s*(?=$CJK)").replace(text) { m ->
            when (m.groupValues[1].ifEmpty { m.groupValues[2] }) {
                "," -> comma
                "?" -> "？"
                "!" -> "！"
                ":" -> "："
                else -> "；"
            }
        }
        out = Regex("(?<=$CJK|[。，、？！])\\s+(?=$CJK)").replace(out, "")
        return out
    }

    /** A Chinese or Japanese character, for [cjkPunctuation]. */
    private const val CJK = "[\\p{IsHan}\\p{IsHiragana}\\p{IsKatakana}]"

    /** The mark that ends a sentence in [language]. */
    fun fullStop(language: String): String = when (language) {
        "ja", "zh" -> "。"
        "hi" -> "।"
        else -> "."
    }

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
            // Not a failure: the download simply has not finished. Kept apart from model_failed.
            FirstRun.step(app, "model_missing")
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
