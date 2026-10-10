package com.voxscribe.android

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/** One finished dictation. */
data class HistoryEntry(val text: String, val atMillis: Long, val durationMillis: Long)

/**
 * Every dictation, newest first, kept on this phone only. Both the floating
 * button and the in-app button write here, and the Flutter screens read it.
 */
object HistoryStore {
    private const val PREFS_NAME = "voxscribe_history"
    private const val KEY_ENTRIES = "entries"
    private const val MAX_ENTRIES = 2000

    private val lock = Any()

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun add(context: Context, entry: HistoryEntry) {
        synchronized(lock) {
            val entries = (listOf(entry) + readAll(context)).take(MAX_ENTRIES)
            val json = JSONArray()
            entries.forEach { json.put(toJson(it)) }
            prefs(context).edit().putString(KEY_ENTRIES, json.toString()).apply()
        }
    }

    fun all(context: Context): List<HistoryEntry> = synchronized(lock) { readAll(context) }

    fun clear(context: Context) {
        synchronized(lock) { prefs(context).edit().remove(KEY_ENTRIES).apply() }
    }

    private fun readAll(context: Context): List<HistoryEntry> {
        val raw = prefs(context).getString(KEY_ENTRIES, null) ?: return emptyList()
        return runCatching {
            val json = JSONArray(raw)
            (0 until json.length()).map { fromJson(json.getJSONObject(it)) }
        }.getOrDefault(emptyList())
    }

    private fun toJson(entry: HistoryEntry) = JSONObject()
        .put("text", entry.text)
        .put("at", entry.atMillis)
        .put("ms", entry.durationMillis)

    private fun fromJson(json: JSONObject) = HistoryEntry(
        text = json.getString("text"),
        atMillis = json.getLong("at"),
        durationMillis = json.getLong("ms"),
    )
}
