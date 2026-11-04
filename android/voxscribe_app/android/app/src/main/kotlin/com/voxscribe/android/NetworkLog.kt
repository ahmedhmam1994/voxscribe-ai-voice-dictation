package com.voxscribe.android

import android.content.Context
import java.net.URI

/**
 * The privacy receipt: every time VoxScribe goes online from this phone, what
 * for, where to and what it sent, kept on the phone so the user can check it.
 * Only the app's own requests are listed (update check, Pro activation, usage
 * ping); none of them ever carries audio or dictated text.
 */
object NetworkLog {
    data class Entry(val atMillis: Long, val what: String, val host: String, val sent: String)

    const val MAX_ENTRIES = 200
    private const val PREFS = "voxscribe_network_log"
    private const val KEY_ENTRIES = "entries"

    /** Adds a request to the receipt. Safe from any thread. */
    @Synchronized
    fun record(context: Context, what: String, url: String, sent: String) {
        val prefs = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val kept = decode(prefs.getString(KEY_ENTRIES, "").orEmpty())
        val entry = Entry(System.currentTimeMillis(), what, hostOf(url), sent)
        prefs.edit().putString(KEY_ENTRIES, encode((kept + entry).takeLast(MAX_ENTRIES))).apply()
    }

    /** Newest first. */
    @Synchronized
    fun entries(context: Context): List<Entry> {
        val prefs = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        return decode(prefs.getString(KEY_ENTRIES, "").orEmpty()).reversed()
    }

    fun hostOf(url: String): String = runCatching { URI(url).host }.getOrNull() ?: url

    // One entry per line, fields split by tabs; tabs and line breaks never appear inside a field.
    private fun clean(field: String): String = field.replace(Regex("[\\t\\r\\n]+"), " ")

    fun encode(entries: List<Entry>): String =
        entries.joinToString("\n") { e -> listOf(e.atMillis.toString(), e.what, e.host, e.sent).joinToString("\t") { clean(it) } }

    fun decode(text: String): List<Entry> = text.lines().mapNotNull { line ->
        val parts = line.split("\t")
        val at = parts.getOrNull(0)?.toLongOrNull() ?: return@mapNotNull null
        if (parts.size != 4) return@mapNotNull null
        Entry(at, parts[1], parts[2], parts[3])
    }
}
