package com.voxscribe.android

import android.content.Context

/**
 * Typed wrapper over SharedPreferences -- every read/write for user-facing
 * settings goes through here so the keys and defaults live in exactly one
 * place, shared between the app UI and the
 * services.
 */
object SettingsStore {
    private const val PREFS_NAME = "voxscribe_settings"

    private const val KEY_PREFER_WHISPER = "prefer_whisper"
    private const val KEY_FALLBACK_LANGUAGE = "fallback_language"
    private const val KEY_CLEANUP_ENABLED = "cleanup_enabled"
    private const val KEY_TRAILING_SPACE = "trailing_space"
    private const val KEY_WHISPER_LANGUAGE = "whisper_language"
    private const val DEFAULT_WHISPER_LANGUAGE = "en"
    private const val KEY_THEME_MODE = "theme_mode"
    private const val KEY_USAGE_PING = "usage_ping"
    private const val KEY_LAST_PING_DAY = "last_ping_day"
    private const val KEY_ANONYMOUS_ID = "anonymous_id"

    /** BCP-47 tag -> display name shown in the language picker. Null tag means "device default". */
    val FALLBACK_LANGUAGES: List<Pair<String?, String>> = listOf(
        null to "System default",
        "en-US" to "English (US)",
        "es-ES" to "Spanish",
        "fr-FR" to "French",
        "de-DE" to "German",
        "it-IT" to "Italian",
        "pt-BR" to "Portuguese",
        "tr-TR" to "Turkish",
        "ar-SA" to "Arabic",
        "hi-IN" to "Hindi",
        "zh-CN" to "Chinese",
        "ja-JP" to "Japanese",
        "ko-KR" to "Korean",
    )

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    /** Prefer the bundled Whisper model when it's available. Off = always use the online/fallback recognizer. */
    fun preferWhisper(context: Context): Boolean =
        prefs(context).getBoolean(KEY_PREFER_WHISPER, true)

    fun setPreferWhisper(context: Context, value: Boolean) {
        prefs(context).edit().putBoolean(KEY_PREFER_WHISPER, value).apply()
    }

    /** BCP-47 language tag for the Milestone 1 fallback recognizer, or null for device default. */
    fun fallbackLanguage(context: Context): String? =
        prefs(context).getString(KEY_FALLBACK_LANGUAGE, null)

    fun setFallbackLanguage(context: Context, tag: String?) {
        prefs(context).edit().putString(KEY_FALLBACK_LANGUAGE, tag).apply()
    }

    /** Strip filler words ("um", "uh", "like", "you know") via TranscriptCleanup. */
    fun cleanupEnabled(context: Context): Boolean =
        prefs(context).getBoolean(KEY_CLEANUP_ENABLED, true)

    fun setCleanupEnabled(context: Context, value: Boolean) {
        prefs(context).edit().putBoolean(KEY_CLEANUP_ENABLED, value).apply()
    }

    /**
     * Language Whisper transcribes in: a code such as "en" or "ar", or an
     * empty string to auto-detect. English by default, because auto-detect
     * guessed Arabic for English speech on a phone microphone.
     */
    fun whisperLanguage(context: Context): String =
        prefs(context).getString(KEY_WHISPER_LANGUAGE, DEFAULT_WHISPER_LANGUAGE)
            ?: DEFAULT_WHISPER_LANGUAGE

    fun setWhisperLanguage(context: Context, code: String) {
        prefs(context).edit().putString(KEY_WHISPER_LANGUAGE, code).apply()
    }

    /** The app theme: "system", "light" or "dark". */
    fun themeMode(context: Context): String =
        prefs(context).getString(KEY_THEME_MODE, "system") ?: "system"

    fun setThemeMode(context: Context, value: String) {
        prefs(context).edit().putString(KEY_THEME_MODE, value).apply()
    }

    /** The once-a-day anonymous launch ping (see [Telemetry]). On by default, as on Windows. */
    fun usagePingEnabled(context: Context): Boolean =
        prefs(context).getBoolean(KEY_USAGE_PING, true)

    fun setUsagePingEnabled(context: Context, value: Boolean) {
        prefs(context).edit().putBoolean(KEY_USAGE_PING, value).apply()
    }

    fun lastPingDay(context: Context): String? = prefs(context).getString(KEY_LAST_PING_DAY, null)

    fun setLastPingDay(context: Context, day: String) {
        prefs(context).edit().putString(KEY_LAST_PING_DAY, day).apply()
    }

    /** A random id made on this phone, so a repeat launch is not counted as a new person. */
    fun anonymousId(context: Context): String? = prefs(context).getString(KEY_ANONYMOUS_ID, null)

    fun setAnonymousId(context: Context, id: String) {
        prefs(context).edit().putString(KEY_ANONYMOUS_ID, id).apply()
    }

    /** Append a trailing space after committing dictated text. */
    fun trailingSpaceEnabled(context: Context): Boolean =
        prefs(context).getBoolean(KEY_TRAILING_SPACE, true)

    fun setTrailingSpaceEnabled(context: Context, value: Boolean) {
        prefs(context).edit().putBoolean(KEY_TRAILING_SPACE, value).apply()
    }
}
