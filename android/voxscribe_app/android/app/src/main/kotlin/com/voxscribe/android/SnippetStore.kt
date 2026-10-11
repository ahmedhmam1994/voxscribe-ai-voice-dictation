package com.voxscribe.android

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/** The user's snippets, in the order they were added. */
object SnippetStore {
    private const val PREFS_NAME = "voxscribe_snippets"
    private const val KEY_SNIPPETS = "snippets"

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun all(context: Context): List<Snippet> {
        val raw = prefs(context).getString(KEY_SNIPPETS, null) ?: return emptyList()
        return runCatching {
            val json = JSONArray(raw)
            (0 until json.length()).map {
                val item = json.getJSONObject(it)
                Snippet(item.getString("trigger"), item.getString("expansion"))
            }
        }.getOrDefault(emptyList())
    }

    fun replaceAll(context: Context, snippets: List<Snippet>) {
        val json = JSONArray()
        snippets.filter { it.trigger.isNotBlank() }.forEach {
            json.put(JSONObject().put("trigger", it.trigger.trim()).put("expansion", it.expansion))
        }
        prefs(context).edit().putString(KEY_SNIPPETS, json.toString()).apply()
    }

    /** Expands [text] when Pro is unlocked and it is a trigger; otherwise returns it unchanged. */
    fun expandIfPro(context: Context, text: String): String =
        if (LicenseStore.isPro(context)) SnippetExpander.expand(text, all(context)) else text
}
