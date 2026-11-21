package com.voxscribe.android

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/** One spoken note: saved, never typed. */
data class Note(val id: Long, val text: String, val atMillis: Long)

/**
 * The notes inbox: say a thought and it is kept here with the time, nothing is
 * typed. Newest first, on this phone only. [markdown] gives the same file the
 * Windows app writes, so the notes can be shared into Obsidian or any notes app.
 */
object NotesStore {
    private const val PREFS_NAME = "voxscribe_notes"
    private const val KEY_NOTES = "notes"
    private const val MAX_NOTES = 5000
    const val TITLE = "# VoxScribe Inbox"

    private val lock = Any()

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    /** Saves [text] as one note. Null when there were no words to keep. */
    fun add(context: Context, text: String, atMillis: Long = System.currentTimeMillis()): Note? {
        val line = oneLine(text)
        if (line.isEmpty()) return null
        synchronized(lock) {
            val existing = readAll(context)
            // Ids only need to be unique on this phone; two notes in the same millisecond still differ.
            val id = maxOf(atMillis, (existing.maxOfOrNull { it.id } ?: 0L) + 1)
            val note = Note(id, line, atMillis)
            write(context, (listOf(note) + existing).take(MAX_NOTES))
            return note
        }
    }

    fun all(context: Context): List<Note> = synchronized(lock) { readAll(context) }

    fun delete(context: Context, id: Long) {
        synchronized(lock) { write(context, readAll(context).filterNot { it.id == id }) }
    }

    fun clear(context: Context) {
        synchronized(lock) { prefs(context).edit().remove(KEY_NOTES).apply() }
    }

    /** The whole inbox as markdown, oldest first, one heading per day. */
    fun markdown(notes: List<Note>, zone: TimeZone = TimeZone.getDefault()): String {
        val day = SimpleDateFormat("yyyy-MM-dd", Locale.US).apply { timeZone = zone }
        val time = SimpleDateFormat("HH:mm", Locale.US).apply { timeZone = zone }
        val out = StringBuilder("$TITLE\n")
        var lastDay: String? = null
        for (note in notes.sortedBy { it.atMillis }) {
            val date = Date(note.atMillis)
            val d = day.format(date)
            if (d != lastDay) {
                out.append("\n## ").append(d).append('\n')
                lastDay = d
            }
            out.append("- ").append(time.format(date)).append(' ').append(note.text).append('\n')
        }
        return out.toString()
    }

    fun oneLine(text: String): String = text.replace(Regex("\\s+"), " ").trim()

    private fun write(context: Context, notes: List<Note>) {
        val json = JSONArray()
        notes.forEach { json.put(JSONObject().put("id", it.id).put("text", it.text).put("at", it.atMillis)) }
        prefs(context).edit().putString(KEY_NOTES, json.toString()).apply()
    }

    private fun readAll(context: Context): List<Note> {
        val raw = prefs(context).getString(KEY_NOTES, null) ?: return emptyList()
        return runCatching {
            val json = JSONArray(raw)
            (0 until json.length()).map {
                val o = json.getJSONObject(it)
                Note(o.getLong("id"), o.getString("text"), o.getLong("at"))
            }
        }.getOrDefault(emptyList())
    }
}
