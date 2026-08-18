package com.voxscribe.android

import android.content.Context

/**
 * Typed wrapper over SharedPreferences -- every read/write for user-facing
 * settings goes through here so the keys and defaults live in exactly one
 * place, shared between SettingsActivity (writes) and
 * VoxScribeInputMethodService (reads).
 */
object SettingsStore {
    private const val PREFS_NAME = "voxscribe_settings"

    private const val KEY_PREFER_WHISPER = "prefer_whisper"
    private const val KEY_FALLBACK_LANGUAGE = "fallback_language"
    private const val KEY_CLEANUP_ENABLED = "cleanup_enabled"
    private const val KEY_TRAILING_SPACE = "trailing_space"

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

    /** Append a trailing space after committing dictated text. */
    fun trailingSpaceEnabled(context: Context): Boolean =
        prefs(context).getBoolean(KEY_TRAILING_SPACE, true)

    fun setTrailingSpaceEnabled(context: Context, value: Boolean) {
        prefs(context).edit().putBoolean(KEY_TRAILING_SPACE, value).apply()
    }
}
