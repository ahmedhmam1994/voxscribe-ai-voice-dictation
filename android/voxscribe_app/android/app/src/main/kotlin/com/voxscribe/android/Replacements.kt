package com.voxscribe.android

/**
 * Custom word replacements: a find-and-replace list applied to every
 * transcription, for words the model keeps getting wrong the same way
 * ("vox scribe" to "VoxScribe"). Free, and the same text format as Windows.
 */
object Replacements {

    /** One "heard => replacement" per line. An empty right side deletes the word. */
    fun parse(text: String): List<Pair<String, String>> =
        text.lines().mapNotNull { line ->
            val arrow = line.indexOf("=>")
            if (arrow < 0) return@mapNotNull null
            val heard = line.substring(0, arrow).trim()
            if (heard.isEmpty()) null else heard to line.substring(arrow + 2).trim()
        }

    /** Case insensitive, whole words only, applied in list order. */
    fun apply(text: String, pairs: List<Pair<String, String>>): String {
        if (text.isEmpty()) return text
        var result = text
        for ((heard, replacement) in pairs) {
            val pattern = Regex("(?<!\\w)" + Regex.escape(heard) + "(?!\\w)", RegexOption.IGNORE_CASE)
            result = pattern.replace(result) { replacement }
        }
        result = Regex("[ \\t]{2,}").replace(result, " ")
        result = Regex("\\s+([,.!?;:])").replace(result) { it.groupValues[1] }
        return result.trim()
    }
}
