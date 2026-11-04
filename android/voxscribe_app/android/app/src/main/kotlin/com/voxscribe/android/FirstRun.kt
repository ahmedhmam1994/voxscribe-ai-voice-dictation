package com.voxscribe.android

import android.app.ActivityManager
import android.content.Context
import android.os.Build
import java.time.LocalDate

/**
 * First-run funnel: where new installs stop before their first dictation, the
 * Android twin of the Windows app's core/firstrun.py. Each step is a fixed event
 * name and, for a failure, a short fixed code ("native", "denied", ...), never
 * an error message, a path, audio or text. It goes out through [Telemetry], so
 * the same random id and the same Settings switch apply.
 *
 * The last step reached is also kept on the phone so Settings can show it to a
 * stuck user ("Copy diagnostics"). That never leaves the phone unless they paste it.
 */
object FirstRun {
    /** A tap shorter than this is a tap, not a dictation. */
    const val TAP_MS = 600L

    /** A range, not the exact time: under_2s, 2_5s, 5_15s or over_15s. */
    fun secondsBucket(seconds: Double): String = when {
        seconds < 2 -> "under_2s"
        seconds < 5 -> "2_5s"
        seconds < 15 -> "5_15s"
        else -> "over_15s"
    }

    /** silent, quiet or normal, from the loudest sample of a recording (0 to 1). */
    fun levelFor(peak: Float): String = when {
        peak < 0.01f -> "silent"
        peak < 0.05f -> "quiet"
        else -> "normal"
    }

    /** missing_files, native, memory or other, from why the speech model failed to load. */
    fun modelCode(error: Throwable?, filesPresent: Boolean): String = when {
        !filesPresent -> "missing_files"
        error is UnsatisfiedLinkError -> "native"
        error is OutOfMemoryError -> "memory"
        else -> "other"
    }

    /** denied when the microphone permission is missing, busy when the recorder would not start. */
    fun micCode(permissionGranted: Boolean): String = if (permissionGranted) "busy" else "denied"

    /** no_field when nothing is focused, service_off when the accessibility service is not running. */
    fun insertCode(serviceRunning: Boolean, focusedInputType: Int): String = when {
        !serviceRunning -> "service_off"
        focusedInputType == 0 -> "no_field"
        else -> "unsupported_field"
    }

    /** activated, bad_key, device_limit, network or other, from the activation reply. */
    fun activationCode(ok: Boolean, message: String): String {
        if (ok) return "activated"
        val text = message.lowercase()
        return when {
            listOf("unable to resolve", "timeout", "timed out", "failed to connect", "network").any { it in text } -> "network"
            listOf("already", "limit", "two ").any { it in text } -> "device_limit"
            listOf("not valid", "invalid", "typos").any { it in text } -> "bad_key"
            else -> "other"
        }
    }

    /** under_3gb, 3_6gb or over_6gb of total memory. */
    fun ramBucket(totalBytes: Long): String {
        val gb = totalBytes / (1024.0 * 1024.0 * 1024.0)
        return when {
            gb < 3 -> "under_3gb"
            gb < 6.5 -> "3_6gb"
            else -> "over_6gb"
        }
    }

    private fun phoneContext(app: Context): Map<String, String> {
        val ram = runCatching {
            val info = ActivityManager.MemoryInfo()
            app.getSystemService(ActivityManager::class.java)?.getMemoryInfo(info)
            ramBucket(info.totalMem)
        }.getOrDefault("")
        return mapOf(
            "manufacturer" to Build.MANUFACTURER.orEmpty().lowercase().take(20),
            "ram" to ram,
        ).filterValues { it.isNotEmpty() }
    }

    val FEATURES = setOf("snippets", "read_back", "file_import", "folder_import", "learned_word", "fast_model", "share_import")

    /** The first time each feature is used, once per install. Only the fixed name is sent. */
    fun feature(context: Context, name: String) {
        if (name in FEATURES) step(context, "feature_used", once = true, extra = mapOf("feature" to name), onceKey = "feature_$name")
    }

    /** Records the step on the phone and sends it: once per install, or at most once a day. */
    fun step(
        context: Context,
        event: String,
        code: String = "",
        once: Boolean = false,
        extra: Map<String, String> = emptyMap(),
        onceKey: String = event,
    ) {
        val app = context.applicationContext
        runCatching {
            SettingsStore.setFunnelNote(app, event, code, System.currentTimeMillis())
            val today = LocalDate.now().toString()
            val due = if (once) {
                !SettingsStore.funnelOnceSent(app, onceKey)
            } else {
                SettingsStore.funnelDay(app, event) != today
            }
            if (!due || !SettingsStore.usagePingEnabled(app)) return
            if (once) SettingsStore.setFunnelOnceSent(app, onceKey) else SettingsStore.setFunnelDay(app, event, today)
            val codeProp = if (code.isNotEmpty()) mapOf("code" to code) else emptyMap()
            Telemetry.sendFunnel(app, event, phoneContext(app) + extra + codeProp)
        }
    }

    /** A short plain-text report for Settings > Copy diagnostics. No audio, text or other apps. */
    fun diagnosticsText(context: Context): String {
        val app = context.applicationContext
        val (step, code, at) = SettingsStore.funnelNote(app)
        val version = runCatching { app.packageManager.getPackageInfo(app.packageName, 0).versionName }
            .getOrNull().orEmpty()
        val last = if (step.isEmpty()) "none yet" else step + (if (code.isNotEmpty()) " ($code)" else "")
        val whenText = if (at > 0) {
            java.text.SimpleDateFormat("yyyy-MM-dd HH:mm", java.util.Locale.US).format(java.util.Date(at))
        } else {
            "never"
        }
        val ram = phoneContext(app)["ram"] ?: "unknown"
        return listOf(
            "VoxScribe for Android $version",
            "Android ${Build.VERSION.RELEASE}, ${Build.MANUFACTURER} ${Build.MODEL}, memory $ram",
            "Last step: $last at $whenText",
            "Speech model: ${if (WhisperEngine.isAvailable(app)) "loaded" else "not loaded"}",
        ).joinToString("\n")
    }
}
