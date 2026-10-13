package com.voxscribe.android

import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

/** A named block of text with {slots}. Say "template <name>" and each slot is asked for in turn. */
data class Template(val name: String, val body: String)

/**
 * Fill-in templates, a Pro feature: a port of the Windows app's logic. A
 * template is spoken for ("template bug report"), then each slot is asked for
 * by voice; once the last is answered, the finished text is typed.
 */
object Templates {
    private val slotRe = Regex("\\{([A-Za-z][A-Za-z0-9 _-]*)\\}")

    /** Filled in automatically, never asked for. */
    private val autoSlots = setOf("date", "time")
    private val triggerWords = listOf("template", "fill")
    private val cancelWords = setOf("cancel", "cancel template", "stop")
    private val skipWords = setOf("skip", "next", "skip this")

    fun normalize(text: String): String =
        text.replace(Regex("[^\\w\\s]"), "").trim().lowercase()

    /** The slots to ask for, in order of first appearance, without repeats. */
    fun slotNames(body: String): List<String> {
        val seen = mutableListOf<String>()
        for (match in slotRe.findAll(body)) {
            val name = match.groupValues[1].trim()
            if (name.lowercase() !in autoSlots && name !in seen) seen.add(name)
        }
        return seen
    }

    /** The template named by a spoken "template <name>" or "fill <name>", when that is the whole utterance. */
    fun find(text: String, templates: List<Template>): Template? {
        val spoken = normalize(text)
        return templates.firstOrNull { template ->
            val name = normalize(template.name)
            triggerWords.any { spoken == "$it $name" }
        }
    }

    /** One `name => body` line each; a line break in a body is written as a backslash and n. */
    fun formatLines(items: List<Template>): String =
        items.joinToString("\n") { "${it.name} => ${it.body.replace("\n", "\\n")}" }

    /** The reverse of [formatLines]. Lines without `=>`, a name or a body are skipped. */
    fun parseLines(text: String): List<Template> =
        text.lines().mapNotNull { line ->
            val arrow = line.indexOf("=>")
            if (arrow < 0) return@mapNotNull null
            val name = line.substring(0, arrow).trim()
            val body = line.substring(arrow + 2).trim()
            if (name.isEmpty() || body.isEmpty()) null else Template(name, body.replace("\\n", "\n"))
        }

    /** Drops the full stop the model adds after a one sentence answer. */
    private fun tidyAnswer(spoken: String): String {
        var answer = spoken.trim()
        if (answer.endsWith(".") && answer.count { it == '.' } == 1) answer = answer.dropLast(1)
        return answer
    }

    /** One template being filled by voice, a slot at a time. */
    class Session(private val template: Template, private val now: LocalDateTime = LocalDateTime.now()) {
        private val slots = slotNames(template.body)
        private val values = linkedMapOf<String, String>()

        val name: String get() = template.name

        /** The slot being asked for, or null once every slot is answered. */
        val prompt: String? get() = if (values.size < slots.size) slots[values.size] else null
        val finished: Boolean get() = prompt == null

        /** Takes one spoken answer. Returns "cancel", "skip" or "filled". */
        fun feed(spoken: String): String {
            val said = normalize(spoken)
            if (said in cancelWords) return "cancel"
            val slot = prompt ?: return "filled"
            if (said in skipWords) {
                values[slot] = ""
                return "skip"
            }
            values[slot] = tidyAnswer(spoken)
            return "filled"
        }

        /** The template text with every answered slot filled in. */
        fun result(): String = slotRe.replace(template.body) { match ->
            val slotName = match.groupValues[1].trim()
            when (slotName.lowercase()) {
                "date" -> now.format(DateTimeFormatter.ISO_LOCAL_DATE)
                "time" -> now.format(DateTimeFormatter.ofPattern("HH:mm"))
                else -> values[slotName] ?: ""
            }
        }
    }
}
