package com.voxscribe.android

/**
 * Repairs the punctuation the fast English model leaves out. It writes a
 * capital letter when a new sentence starts but often skips the full stop
 * before it, and the last sentence of a dictation can end bare.
 *
 *   "starts on monday at 9:30 AM The first phase"  gives "... 9:30 AM. The first phase"
 *   "we will talk about it later" (4+ words)       gets a closing full stop
 *
 * Conservative: only an unmistakable sentence opener written with a capital
 * gets a full stop in front of it, and never after a word that cannot end a
 * sentence (a preposition, an article, a conjunction), so titles like "Lord of
 * The Rings" are left alone.
 */
object SentenceFix {

    /** Words that start a sentence and are rarely capitalised in the middle of one. */
    private val openers = setOf(
        "the", "we", "please", "if", "it", "this", "that", "they", "then", "also", "there",
        "our", "my", "you", "but", "so", "and", "can", "could", "would", "should", "let",
        "thanks", "thank", "i'll", "i'm", "i've", "i'd", "what", "when", "how", "why", "where",
        "he", "she", "these", "those", "once", "after", "before", "because", "however",
    )

    /** A word before which a capital cannot mean a new sentence. */
    private val cannotEnd = setOf(
        "of", "in", "on", "at", "to", "for", "with", "by", "from", "into", "onto", "about",
        "and", "or", "but", "nor", "so", "the", "a", "an", "my", "our", "your", "his", "her",
        "their", "its", "is", "are", "was", "were", "be", "been", "that", "than", "as", "if",
        "not", "no", "very", "more", "most", "some", "any", "each", "every", "all", "both",
        "dear", "hi", "hello", "hey", "mr", "mrs", "ms", "dr", "st", "vs",
    )

    private val wordRe = Regex("(\\S+)(\\s+)(?=([A-Z][A-Za-z']*))")

    /** Adds the missing full stops between sentences. */
    fun splitSentences(text: String): String {
        if (text.isEmpty()) return text
        return wordRe.replace(text) { m ->
            val previous = m.groupValues[1]
            val opener = m.groupValues[3]
            val last = previous.last()
            val bare = last.isLetterOrDigit() || last == '%' || last == ')'
            val previousWord = previous.trimEnd('.').lowercase()
            if (bare && opener.lowercase() in openers && previousWord !in cannotEnd) {
                previous + "." + m.groupValues[2]
            } else {
                m.value
            }
        }
    }

    /** A closing full stop for a dictation of four words or more that ends bare. */
    fun closeSentence(text: String): String {
        val trimmed = text.trimEnd()
        if (trimmed.isEmpty()) return text
        val last = trimmed.last()
        if (!(last.isLetterOrDigit() || last == '%')) return text
        if (trimmed.split(Regex("\\s+")).size < 4) return text
        // Not a web address, an email or a number on its own.
        if (trimmed.contains('@') || trimmed.contains("://")) return text
        return trimmed + "." + text.substring(trimmed.length)
    }

    fun fix(text: String, closeEnd: Boolean = true): String {
        val split = splitSentences(text)
        return if (closeEnd) closeSentence(split) else split
    }
}
