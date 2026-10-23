package com.voxscribe.android

import android.content.Context
import android.os.Build
import java.net.HttpURLConnection
import java.net.URL
import java.time.LocalDate
import java.util.UUID

/**
 * Anonymous usage pings, the Android twin of the Windows app's core/telemetry.py,
 * so there are real numbers on how many people use the app and not just how many
 * downloaded it. Three events to PostHog:
 * - "app_launched", at most once a day, when the app or the floating button
 *   starts (the button runs on its own and people rarely open the app itself).
 * - "first_dictation", once per install, the first time a dictation is saved.
 * - "dictated_today", at most once a day, when a dictation is saved that day.
 *
 * Each sends the app version, the Android version and a random id made on the
 * phone. Never audio, never text, no word counts, nothing about other apps,
 * nothing that names the person. All three are off with the one switch in
 * Settings. Any failure is ignored: telemetry must never slow down or break
 * dictation.
 */
object Telemetry {
    // Project key: it can only send events, not read anything (same key as Windows).
    private const val API_KEY = "phc_vkYFuUzTmMNT4bUffuMjiNSMnAqkQgPEp3vCHYrzFWoH"
    private const val ENDPOINT = "https://us.i.posthog.com/capture/"
    private const val TIMEOUT_MS = 8_000

    /** True when today's ping has not gone out yet and the user allows it. */
    fun shouldSend(enabled: Boolean, lastSentDay: String?, today: String): Boolean =
        enabled && lastSentDay != today

    /** Which events a saved dictation should send: the first ever, and the first of each day. */
    fun eventsForDictation(enabled: Boolean, firstSent: Boolean, lastDay: String?, today: String): List<String> {
        if (!enabled) return emptyList()
        val events = mutableListOf<String>()
        if (!firstSent) events += "first_dictation"
        if (lastDay != today) events += "dictated_today"
        return events
    }

    /** The event, as PostHog's capture API takes it. */
    fun payload(distinctId: String, appVersion: String, osVersion: String, event: String = "app_launched"): String =
        """{"api_key":"${escape(API_KEY)}","event":"${escape(event)}","distinct_id":"${escape(distinctId)}",""" +
            """"properties":{"app_version":"${escape(appVersion)}","os":"Android",""" +
            """"os_version":"${escape(osVersion)}","platform":"android"}}"""

    private fun escape(value: String): String =
        value.replace("\\", "\\\\").replace("\"", "\\\"").filter { it >= ' ' }

    fun sendIfDue(context: Context) {
        val app = context.applicationContext
        val today = LocalDate.now().toString()
        if (!shouldSend(SettingsStore.usagePingEnabled(app), SettingsStore.lastPingDay(app), today)) return
        // Marked before sending, so the app and the button starting together send one ping.
        SettingsStore.setLastPingDay(app, today)
        post(app, "app_launched")
    }

    /**
     * Call after a dictation was saved. Sends "first_dictation" once ever and
     * "dictated_today" once a day. Nothing is marked as sent while the user has
     * the ping switched off, so turning it on later starts counting from the
     * next dictation.
     */
    fun sendDictationUsed(context: Context) {
        val app = context.applicationContext
        val today = LocalDate.now().toString()
        val events = eventsForDictation(
            enabled = SettingsStore.usagePingEnabled(app),
            firstSent = SettingsStore.firstDictationSent(app),
            lastDay = SettingsStore.lastDictationDay(app),
            today = today,
        )
        if (events.isEmpty()) return
        // Marked before sending, so two dictations in a row send each event once.
        SettingsStore.setFirstDictationSent(app)
        SettingsStore.setLastDictationDay(app, today)
        events.forEach { post(app, it) }
    }

    private fun post(app: Context, event: String) {
        val body = payload(anonymousId(app), appVersion(app), Build.VERSION.RELEASE.orEmpty(), event)
        Thread {
            try {
                val connection = URL(ENDPOINT).openConnection() as HttpURLConnection
                connection.requestMethod = "POST"
                connection.connectTimeout = TIMEOUT_MS
                connection.readTimeout = TIMEOUT_MS
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json")
                connection.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
                connection.responseCode
                connection.disconnect()
            } catch (e: Exception) {
                // No network, PostHog unreachable: try again on another day.
            }
        }.start()
    }

    private fun anonymousId(context: Context): String =
        SettingsStore.anonymousId(context) ?: UUID.randomUUID().toString().also {
            SettingsStore.setAnonymousId(context, it)
        }

    private fun appVersion(context: Context): String = try {
        context.packageManager.getPackageInfo(context.packageName, 0).versionName.orEmpty()
    } catch (e: Exception) {
        ""
    }
}
