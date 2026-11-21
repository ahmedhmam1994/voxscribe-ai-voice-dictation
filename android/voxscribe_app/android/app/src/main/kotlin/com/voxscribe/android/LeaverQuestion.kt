package com.voxscribe.android

import android.content.Context
import java.time.LocalDate
import java.time.temporal.ChronoUnit

/**
 * A one-time question for someone who stopped dictating: after [QUIET_DAYS]
 * without a dictation, the next time they open the app it asks once why, with
 * fixed choices only. The answer goes out as one usage ping with the choice's
 * key, so it is only asked while the ping is on. Never asked again, whatever
 * they pick, including "don't ask".
 */
object LeaverQuestion {
    const val QUIET_DAYS = 5

    /** The answers the app offers, by the key the ping sends. */
    val REASONS = listOf(
        "wrong_words", "too_slow", "no_text", "button_in_way",
        "button_gone", "forgot", "rarely_need", "busy", "other",
    )

    fun isDue(pingOn: Boolean, asked: Boolean, lastUseDay: String?, today: LocalDate): Boolean {
        if (!pingOn || asked || lastUseDay == null) return false
        val last = runCatching { LocalDate.parse(lastUseDay) }.getOrNull() ?: return false
        return ChronoUnit.DAYS.between(last, today) >= QUIET_DAYS
    }

    fun isDue(context: Context): Boolean = isDue(
        pingOn = SettingsStore.usagePingEnabled(context),
        asked = SettingsStore.leaverAsked(context),
        // Before this version only the ping kept the day, so fall back to it for existing users.
        lastUseDay = SettingsStore.lastUseDay(context) ?: SettingsStore.lastDictationDay(context),
        today = LocalDate.now(),
    )

    /** [reason] null means they chose not to answer: nothing is sent. */
    fun answer(context: Context, reason: String?) {
        SettingsStore.setLeaverAsked(context)
        if (reason in REASONS && SettingsStore.usagePingEnabled(context)) {
            Telemetry.sendLeaverAnswer(context, reason!!)
        }
    }
}
