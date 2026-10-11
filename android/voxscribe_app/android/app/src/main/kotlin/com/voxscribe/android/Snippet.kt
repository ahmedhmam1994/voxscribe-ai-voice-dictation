package com.voxscribe.android

import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

/** Say [trigger] on its own and [expansion] is typed instead. */
data class Snippet(val trigger: String, val expansion: String)

/** Swaps a spoken trigger for its longer text. A Pro feature, entirely on the phone. */
object SnippetExpander {
    /**
     * If [text] is exactly a trigger (ignoring case and end punctuation),
     * returns that snippet's expansion with `{date}` and `{time}` filled in.
     * Anything else comes back unchanged, because a trigger is used on its own.
     */
    fun expand(text: String, snippets: List<Snippet>, now: LocalDateTime = LocalDateTime.now()): String {
        val spoken = normalize(text)
        val match = snippets.firstOrNull { normalize(it.trigger) == spoken } ?: return text
        return match.expansion
            .replace("{date}", now.format(DateTimeFormatter.ISO_LOCAL_DATE))
            .replace("{time}", now.format(DateTimeFormatter.ofPattern("HH:mm")))
    }

    private fun normalize(text: String) = text.trim().trim('.', '!', '?').trim().lowercase()
}
