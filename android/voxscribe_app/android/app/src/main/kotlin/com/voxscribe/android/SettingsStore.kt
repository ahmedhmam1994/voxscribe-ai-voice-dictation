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

    private const val KEY_CLEANUP_ENABLED = "cleanup_enabled"
    private const val KEY_TRAILING_SPACE = "trailing_space"
    // Named from when Whisper was the model; kept so a saved choice survives the update.
    private const val KEY_LANGUAGE = "whisper_language"
    private const val KEY_THEME_MODE = "theme_mode"
    private const val KEY_USAGE_PING = "usage_ping"
    private const val KEY_LAST_PING_DAY = "last_ping_day"
    private const val KEY_ANONYMOUS_ID = "anonymous_id"
    private const val KEY_RECORDING_MODE = "recording_mode"
    private const val KEY_BUBBLE_SIZE = "bubble_size"
    private const val KEY_TAP_HINT_SHOWN = "tap_hint_shown"
    private const val KEY_FIRST_DICTATION_SENT = "first_dictation_sent"
    private const val KEY_LAST_DICTATION_DAY = "last_dictation_day"
    private const val KEY_SETUP_EVENTS_SENT = "setup_events_sent"
    private const val KEY_SETUP_SEEN = "setup_seen"
    private const val KEY_BUBBLE_USED = "bubble_used"
    private const val KEY_HANDS_FREE = "hands_free"
    private const val KEY_LAST_USE_DAY = "last_use_day"
    private const val KEY_LEAVER_ASKED = "leaver_asked"

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    /** Strip filler words ("um", "uh", "like", "you know") via TranscriptCleanup. */
    fun cleanupEnabled(context: Context): Boolean =
        prefs(context).getBoolean(KEY_CLEANUP_ENABLED, true)

    fun setCleanupEnabled(context: Context, value: Boolean) {
        prefs(context).edit().putBoolean(KEY_CLEANUP_ENABLED, value).apply()
    }

    /**
     * The language the user speaks, as a code from [SpeechEngine.LANGUAGES].
     * Until one is picked it is the phone's own language when the models
     * type it, else English. Auto-detect ("") was dropped with Whisper, and a
     * saved code the models do not type is treated the same way.
     */
    fun language(context: Context): String {
        val saved = prefs(context).getString(KEY_LANGUAGE, null)
        if (saved != null && saved in SpeechEngine.LANGUAGES) return saved
        val phone = java.util.Locale.getDefault().language
        return if (phone in SpeechEngine.LANGUAGES) phone else "en"
    }

    fun setLanguage(context: Context, code: String) {
        prefs(context).edit().putString(KEY_LANGUAGE, code).apply()
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

    // First-run funnel (see [FirstRun]): which steps went out, and the last one reached.
    fun funnelOnceSent(context: Context, event: String): Boolean =
        prefs(context).getBoolean("funnel_once_$event", false)

    fun setFunnelOnceSent(context: Context, event: String) {
        prefs(context).edit().putBoolean("funnel_once_$event", true).apply()
    }

    fun funnelDay(context: Context, event: String): String? = prefs(context).getString("funnel_day_$event", null)

    fun setFunnelDay(context: Context, event: String, day: String) {
        prefs(context).edit().putString("funnel_day_$event", day).apply()
    }

    /** True while the floating button's service is alive; still true at the next start means it was killed. */
    fun bubbleAlive(context: Context): Boolean = prefs(context).getBoolean("bubble_alive", false)

    fun setBubbleAlive(context: Context, alive: Boolean) {
        prefs(context).edit().putBoolean("bubble_alive", alive).apply()
    }

    /** The user turned the floating button on and has not turned it off, so it should come back after Android stops it. */
    fun bubbleWanted(context: Context): Boolean = prefs(context).getBoolean("bubble_wanted", false)

    fun setBubbleWanted(context: Context, wanted: Boolean) {
        prefs(context).edit().putBoolean("bubble_wanted", wanted).apply()
    }

    /** The "phone closed VoxScribe" notification was shown for the current break. */
    fun brokenNotified(context: Context): Boolean = prefs(context).getBoolean("broken_notified", false)

    fun setBrokenNotified(context: Context, notified: Boolean) {
        prefs(context).edit().putBoolean("broken_notified", notified).apply()
    }

    /** The Xiaomi tips (Autostart, lock in recent apps) were read and closed. */
    fun xiaomiTipsDone(context: Context): Boolean = prefs(context).getBoolean("xiaomi_tips_done", false)

    fun setXiaomiTipsDone(context: Context) {
        prefs(context).edit().putBoolean("xiaomi_tips_done", true).apply()
    }

    /** When setup sent the user to the accessibility switch, so the app can come back once it is on. */
    fun accessibilityAskedAt(context: Context): Long = prefs(context).getLong("accessibility_asked_at", 0L)

    fun setAccessibilityAskedAt(context: Context, atMillis: Long) {
        prefs(context).edit().putLong("accessibility_asked_at", atMillis).apply()
    }

    fun setFunnelNote(context: Context, step: String, code: String, atMillis: Long) {
        prefs(context).edit()
            .putString("funnel_last_step", step).putString("funnel_last_code", code)
            .putLong("funnel_last_at", atMillis).apply()
    }

    /** The last funnel step reached: name, code and time in milliseconds. */
    fun funnelNote(context: Context): Triple<String, String, Long> {
        val p = prefs(context)
        return Triple(
            p.getString("funnel_last_step", "").orEmpty(),
            p.getString("funnel_last_code", "").orEmpty(),
            p.getLong("funnel_last_at", 0L),
        )
    }

    /** The one-time "first_dictation" ping has gone out (see [Telemetry]). */
    fun firstDictationSent(context: Context): Boolean = prefs(context).getBoolean(KEY_FIRST_DICTATION_SENT, false)

    fun setFirstDictationSent(context: Context) {
        prefs(context).edit().putBoolean(KEY_FIRST_DICTATION_SENT, true).apply()
    }

    /** The day the last "dictated_today" ping went out, as yyyy-MM-dd. */
    fun lastDictationDay(context: Context): String? = prefs(context).getString(KEY_LAST_DICTATION_DAY, null)

    fun setLastDictationDay(context: Context, day: String) {
        prefs(context).edit().putString(KEY_LAST_DICTATION_DAY, day).apply()
    }

    /**
     * The one-time setup pings already handled (see [Telemetry.setupEvents]),
     * or null before the app has looked at the setup steps for the first time.
     */
    fun setupEventsSent(context: Context): Set<String>? =
        prefs(context).getStringSet(KEY_SETUP_EVENTS_SENT, null)?.toSet()

    fun setSetupEventsSent(context: Context, events: Set<String>) {
        prefs(context).edit().putStringSet(KEY_SETUP_EVENTS_SENT, events).apply()
    }

    /**
     * The setup screen has been opened on this phone. A new install starts on
     * the setup steps until then. Installs from before this flag existed have
     * been updated at least once, so they count as seen.
     */
    fun setupSeen(context: Context): Boolean =
        prefs(context).getBoolean(KEY_SETUP_SEEN, false) || updatedSinceInstall(context)

    fun setSetupSeen(context: Context) {
        prefs(context).edit().putBoolean(KEY_SETUP_SEEN, true).apply()
    }

    /**
     * The floating button has been pressed at least once. Until then the app
     * offers a practice box. Updated installs count as used, as above.
     */
    fun bubbleUsed(context: Context): Boolean =
        prefs(context).getBoolean(KEY_BUBBLE_USED, false) || updatedSinceInstall(context)

    fun setBubbleUsed(context: Context) {
        if (!prefs(context).getBoolean(KEY_BUBBLE_USED, false)) {
            prefs(context).edit().putBoolean(KEY_BUBBLE_USED, true).apply()
        }
    }

    private fun updatedSinceInstall(context: Context): Boolean = runCatching {
        val info = context.packageManager.getPackageInfo(context.packageName, 0)
        info.lastUpdateTime > info.firstInstallTime
    }.getOrDefault(false)

    /** A random id made on this phone, so a repeat launch is not counted as a new person. */
    fun anonymousId(context: Context): String? = prefs(context).getString(KEY_ANONYMOUS_ID, null)

    fun setAnonymousId(context: Context, id: String) {
        prefs(context).edit().putString(KEY_ANONYMOUS_ID, id).apply()
    }

    /** How the floating button reacts to a touch: "both" (default), "hold" or "tap". See [HoldOrTap.Mode]. */
    fun recordingMode(context: Context): HoldOrTap.Mode =
        HoldOrTap.Mode.fromKey(prefs(context).getString(KEY_RECORDING_MODE, null))

    fun setRecordingMode(context: Context, mode: HoldOrTap.Mode) {
        prefs(context).edit().putString(KEY_RECORDING_MODE, mode.key).apply()
    }

    /** The size of the floating button: "small", "medium" (default) or "large". */
    fun bubbleSize(context: Context): BubbleSize =
        BubbleSize.fromKey(prefs(context).getString(KEY_BUBBLE_SIZE, null))

    fun setBubbleSize(context: Context, size: BubbleSize) {
        prefs(context).edit().putString(KEY_BUBBLE_SIZE, size.key).apply()
    }

    /** The one-time "tap once to start" tip has been shown. */
    fun tapHintShown(context: Context): Boolean = prefs(context).getBoolean(KEY_TAP_HINT_SHOWN, false)

    fun setTapHintShown(context: Context) {
        prefs(context).edit().putBoolean(KEY_TAP_HINT_SHOWN, true).apply()
    }

    /** Append a trailing space after committing dictated text. */
    fun trailingSpaceEnabled(context: Context): Boolean =
        prefs(context).getBoolean(KEY_TRAILING_SPACE, true)

    fun setTrailingSpaceEnabled(context: Context, value: Boolean) {
        prefs(context).edit().putBoolean(KEY_TRAILING_SPACE, value).apply()
    }

    /** The last day a dictation was saved, kept whether or not the ping is on (see [LeaverQuestion]). */
    fun lastUseDay(context: Context): String? = prefs(context).getString(KEY_LAST_USE_DAY, null)

    fun setLastUseDay(context: Context, day: String) {
        prefs(context).edit().putString(KEY_LAST_USE_DAY, day).apply()
    }

    fun leaverAsked(context: Context): Boolean = prefs(context).getBoolean(KEY_LEAVER_ASKED, false)

    fun setLeaverAsked(context: Context) {
        prefs(context).edit().putBoolean(KEY_LEAVER_ASKED, true).apply()
    }

    /** Pro: a tap on the floating button keeps listening and types each phrase when you pause. */
    fun handsFree(context: Context): Boolean = prefs(context).getBoolean(KEY_HANDS_FREE, false)

    fun setHandsFree(context: Context, value: Boolean) {
        prefs(context).edit().putBoolean(KEY_HANDS_FREE, value).apply()
    }
}
