package com.voxscribe.android

/**
 * Spoken punctuation and formatting commands ("period", "new line", ...) plus
 * the spoken editing phrases ("scratch that", "delete last word"). A port of
 * the Windows app's voice commands, kept behaviour for behaviour.
 *
 * Opt in, because someone who says the literal word "period" or "comma"
 * mid-sentence would otherwise get a symbol instead of the word.
 */
object VoiceCommands {

    private enum class Kind { END, MID, NEWLINE, OPEN, CLOSE }

    private data class Command(val phrase: String, val symbol: String, val kind: Kind)

    // Multi-word phrases are listed before the shorter ones they could start.
    private val commands = listOf(
        Command("new paragraph", "\n\n", Kind.NEWLINE),
        Command("new line", "\n", Kind.NEWLINE),
        Command("question mark", "?", Kind.END),
        Command("exclamation mark", "!", Kind.END),
        Command("exclamation point", "!", Kind.END),
        Command("open quote", "\"", Kind.OPEN),
        Command("close quote", "\"", Kind.CLOSE),
        Command("open parenthesis", "(", Kind.OPEN),
        Command("close parenthesis", ")", Kind.CLOSE),
        Command("open paren", "(", Kind.OPEN),
        Command("close paren", ")", Kind.CLOSE),
        Command("full stop", ".", Kind.END),
        Command("period", ".", Kind.END),
        Command("comma", ",", Kind.MID),
        Command("colon", ":", Kind.MID),
        Command("semicolon", ";", Kind.MID),
    )

    /** Marks a spot where the next letter is capitalized; removed in the last pass. */
    private const val CAP_MARK = ''

    private val spaceBeforePunct = Regex("[ \\t]+([,.!?;:])")
    private val spacesAroundNewline = Regex("[ \\t]*\\n[ \\t]*")
    private val multiSpace = Regex("[ \\t]+")
    private val capNextLetter = Regex("$CAP_MARK([ \\t\\n]*)([a-z])")

    private val compiled = commands.map { command ->
        val core = command.phrase.split(" ").joinToString("\\s+") { Regex.escape(it) }
        Triple(Regex("\\s*\\b$core\\b\\s*", RegexOption.IGNORE_CASE), command.symbol, command.kind)
    }

    /** Replaces spoken punctuation and formatting commands with the symbols they name. */
    fun apply(text: String): String {
        if (text.isBlank()) return text
        var result = text
        for ((pattern, symbol, kind) in compiled) {
            val replacement = when (kind) {
                Kind.END -> "$symbol $CAP_MARK"
                Kind.NEWLINE -> "$symbol$CAP_MARK"
                Kind.MID -> "$symbol "
                Kind.OPEN -> " $symbol"
                Kind.CLOSE -> "$symbol "
            }
            result = pattern.replace(result) { replacement }
        }
        result = spaceBeforePunct.replace(result) { it.groupValues[1] }
        result = spacesAroundNewline.replace(result, "\n")
        result = multiSpace.replace(result, " ")
        result = capNextLetter.replace(result) { it.groupValues[1] + it.groupValues[2].uppercase() }
        return result.replace(CAP_MARK.toString(), "").trim()
    }

    /** How much of the last typed text a spoken editing phrase removes. */
    enum class Edit { ALL, WORD, SENTENCE }

    private val editingPhrases = mapOf(
        "delete last word" to Edit.WORD,
        "delete that word" to Edit.WORD,
        "scratch that word" to Edit.WORD,
        "delete last sentence" to Edit.SENTENCE,
        "delete that sentence" to Edit.SENTENCE,
        "scratch that sentence" to Edit.SENTENCE,
        "scratch that" to Edit.ALL,
        "scratch it" to Edit.ALL,
        "scrap that" to Edit.ALL,
        "scrap it" to Edit.ALL,
        "cancel that" to Edit.ALL,
        "undo that" to Edit.ALL,
        "delete that" to Edit.ALL,
        "undo" to Edit.ALL,
    )
    private val trailingPunct = Regex("[.!?]+$")

    /**
     * The editing command when the WHOLE utterance is one, otherwise null.
     * "scratch that itch" is real dictation, not a command.
     */
    fun editingCommand(text: String): Edit? {
        if (text.isEmpty()) return null
        val normalized = trailingPunct.replace(text.trim(), "").trim().lowercase()
        return editingPhrases[normalized] ?: fuzzyEditingCommand(normalized) ?: garbledScratch(normalized)
    }

    private val SCRATCH_FILLERS = setOf("the", "this", "a")

    /**
     * The model often hears "scratch that" as "scratch the toe" or "scrape the
     * top": a scratch-like first word, "the", then a short stray word. Only
     * that exact shape counts, so "scratch the surface" and "scratch that itch"
     * stay dictation.
     */
    private fun garbledScratch(normalized: String): Edit? {
        val words = normalized.split(Regex("\\s+")).filter { it.isNotEmpty() }
        if (words.size != 3) return null
        if (!words[0].startsWith("scra") || words[1] !in SCRATCH_FILLERS || words[2].length > 3) return null
        return Edit.ALL
    }

    /**
     * The phone's speech model is small and often mishears a short command
     * ("scratch that" came out as "Scratch Z." and "Scraach the"). A close
     * enough match still counts, under strict rules so real dictation is left
     * alone: the utterance must have the same number of words as the phrase,
     * the key words ("scratch", "delete", "word", "sentence") must match
     * closely, and only the small filler words ("that", "last", "the") may be
     * misheard. "scratch that itch" and "scratch pad" stay dictation, and a
     * one word phrase such as "undo" is never matched loosely.
     */
    private fun fuzzyEditingCommand(normalized: String): Edit? {
        val words = normalized.split(Regex("\\s+")).filter { it.isNotEmpty() }
        if (words.size < 2) return null
        var best: Pair<Double, Edit>? = null
        for ((phrase, edit) in editingPhrases) {
            val parts = phrase.split(" ")
            if (parts.size != words.size) continue
            var total = 0.0
            val allClose = parts.indices.all { i ->
                val score = similarity(words[i], parts[i])
                total += score
                if (parts[i] in KEY_WORDS) score >= KEY_WORD_MATCH || sharesStart(words[i], parts[i])
                else words[i].length <= 2 || score >= FILLER_MATCH
            }
            if (allClose && (best == null || total > best.first)) best = total to edit
        }
        return best?.second
    }

    private val KEY_WORDS = setOf("scratch", "scrap", "delete", "cancel", "undo", "word", "sentence")

    /** A long key word still counts when the first four letters are right ("scrape" for "scratch"). */
    private fun sharesStart(heard: String, phraseWord: String): Boolean =
        phraseWord.length >= 5 && heard.length >= 4 && heard.take(4) == phraseWord.take(4)

    private const val KEY_WORD_MATCH = 0.7
    private const val FILLER_MATCH = 0.4

    /** 1 for identical text down to 0 for nothing in common, from the edit distance. */
    private fun similarity(a: String, b: String): Double {
        if (a == b) return 1.0
        val longest = maxOf(a.length, b.length)
        if (longest == 0) return 1.0
        var previous = IntArray(b.length + 1) { it }
        for (i in 1..a.length) {
            val current = IntArray(b.length + 1)
            current[0] = i
            for (j in 1..b.length) {
                val cost = if (a[i - 1] == b[j - 1]) 0 else 1
                current[j] = minOf(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost)
            }
            previous = current
        }
        return 1.0 - previous[b.length].toDouble() / longest
    }

    /** Spoken commands that change the text typed last instead of deleting it. */
    enum class Transform { CAPITALIZE, UPPERCASE, LOWERCASE }

    // The small speech model hears "that" as "Z" and "capitalize" as "capitalized", so those
    // count too. The bare keywords are only safe after a pause (see weakTrailing).
    private val transformPhrases: Map<String, Transform> = buildMap {
        val fillers = listOf("that", "it", "z")
        for (key in listOf("capitalize", "capitalise", "capitalized", "capitalised")) {
            for (filler in fillers) put("$key $filler", Transform.CAPITALIZE)
        }
        for (key in listOf("uppercase", "upper case")) {
            for (filler in fillers) put("$key $filler", Transform.UPPERCASE)
        }
        for (key in listOf("lowercase", "lower case")) {
            for (filler in fillers) put("$key $filler", Transform.LOWERCASE)
        }
        put("make that uppercase", Transform.UPPERCASE)
        put("make that lowercase", Transform.LOWERCASE)
        put("all caps", Transform.UPPERCASE)
        put("all caps that", Transform.UPPERCASE)
        put("all lowercase", Transform.LOWERCASE)
        put("capitalize", Transform.CAPITALIZE)
        put("capitalise", Transform.CAPITALIZE)
        put("uppercase", Transform.UPPERCASE)
        put("lowercase", Transform.LOWERCASE)
    }

    private fun normalized(text: String): String = trailingPunct.replace(text.trim(), "").trim().lowercase()

    /** The transform when the WHOLE utterance is one, otherwise null. */
    fun transformCommand(text: String): Transform? =
        if (text.isEmpty()) null else transformPhrases[normalized(text)]

    /** Every word starts with a capital, or the whole text goes up or down. Spacing is kept. */
    fun applyTransform(text: String, transform: Transform): String = when (transform) {
        Transform.UPPERCASE -> text.uppercase()
        Transform.LOWERCASE -> text.lowercase()
        Transform.CAPITALIZE -> Regex("\\S+").replace(text) { match ->
            match.value.replaceFirstChar { c -> if (c.isLowerCase()) c.titlecase() else c.toString() }
        }
    }

    // Phrases that need a pause before them to count at the end of a sentence, because they
    // could just be words ("write it in all caps", "we should capitalize").
    private val weakTrailing = setOf(
        "all caps", "all caps that", "all lowercase", "capitalize", "capitalise", "uppercase", "lowercase",
    ) +
        // "we need to capitalize it" is an ordinary sentence far more often than a
        // command, so the "it" forms need a pause before them too.
        transformPhrases.keys.filter { it.endsWith(" it") }

    private fun alternatives(phrases: Collection<String>): String =
        phrases.sortedByDescending { it.length }.joinToString("|") { Regex.escape(it) }

    private val trailingAfterPause = Regex(
        "^(.+?)\\s*([,.;:!?])\\s*(" + alternatives(transformPhrases.keys) + ")\\s*[.!?]*$",
        RegexOption.IGNORE_CASE,
    )
    private val trailingAnywhere = Regex(
        "^(.+?)\\s+(" + alternatives(transformPhrases.keys - weakTrailing) + ")\\s*[.!?]*$",
        RegexOption.IGNORE_CASE,
    )

    /**
     * "bring the notes, all caps" as ("bring the notes", UPPERCASE): the command at the
     * end of the same sentence, said in one go. A question or exclamation mark before the
     * command stays with the sentence. Null when there is no such ending.
     */
    fun splitTrailingTransform(text: String): Pair<String, Transform>? {
        val trimmed = text.trim()
        val pause = trailingAfterPause.matchEntire(trimmed)
        val (before, mark, phrase) = if (pause != null) {
            Triple(pause.groupValues[1], pause.groupValues[2], pause.groupValues[3])
        } else {
            val plain = trailingAnywhere.matchEntire(trimmed) ?: return null
            Triple(plain.groupValues[1], "", plain.groupValues[2])
        }
        val transform = transformPhrases[phrase.lowercase()] ?: return null
        val sentence = before.trim()
        if (sentence.isEmpty()) return null
        return (if (mark == "?" || mark == "!") sentence + mark else sentence) to transform
    }

    private val replaceRegex = Regex("^replace\\s+(.+?)\\s+with\\s+(.+)$", RegexOption.IGNORE_CASE)

    /**
     * "replace X with Y" as (X, Y), or null. An ordinary sentence can have this
     * shape ("replace the battery with a new one"), so the caller only treats it
     * as a command when X is really in the last dictation, see [applyReplace].
     */
    fun replaceCommand(text: String): Pair<String, String>? {
        val match = replaceRegex.matchEntire(trailingPunct.replace(text.trim(), "").trim()) ?: return null
        val from = match.groupValues[1].trim()
        val to = match.groupValues[2].trim()
        return if (from.isEmpty() || to.isEmpty()) null else from to to
    }

    /** [chunk] with every whole-word, case-insensitive [from] swapped for [to], or null when [from] is not in it. */
    fun applyReplace(chunk: String, from: String, to: String): String? {
        val pattern = Regex(
            "(?<![\\p{L}\\p{N}])" + Regex.escape(from) + "(?![\\p{L}\\p{N}])",
            RegexOption.IGNORE_CASE,
        )
        if (!pattern.containsMatchIn(chunk)) return null
        // A function, not a string, so a "$" or "\" in the replacement is kept as typed.
        return pattern.replace(chunk) { to }
    }

    private val trailingReplaceRegex = Regex(
        "^(.+?)\\s*([,.;:!?])\\s*replace\\s+(.+?)\\s+with\\s+(.+?)\\s*[.!?]*$",
        RegexOption.IGNORE_CASE,
    )

    /**
     * "meet me at noon, replace noon with one" as "meet me at one": a replace said at the
     * end of the same sentence. It only counts when the first phrase is really in the
     * sentence before it, so "I will replace the battery with a new one" stays dictation.
     * Null when there is no such ending.
     */
    fun applyTrailingReplace(text: String): String? {
        val match = trailingReplaceRegex.matchEntire(text.trim()) ?: return null
        val before = match.groupValues[1].trim()
        val from = match.groupValues[3].trim()
        val to = match.groupValues[4].trim()
        if (before.isEmpty() || from.isEmpty() || to.isEmpty()) return null
        val changed = applyReplace(before, from, to) ?: return null
        val mark = match.groupValues[2]
        return if (mark == "?" || mark == "!") changed + mark else changed
    }

    /**
     * SEND taps the app's Send button, because Enter is only a new line in most chat apps.
     * ENTER presses the Enter key itself.
     */
    enum class SendKind { SEND, ENTER }

    private val sendPhrases = mapOf(
        "send it" to SendKind.SEND,
        "send that" to SendKind.SEND,
        "press enter" to SendKind.ENTER,
        "hit enter" to SendKind.ENTER,
        "press return" to SendKind.ENTER,
    )

    /** What the WHOLE utterance asks for, "send it" or "press enter", or null. */
    fun sendCommand(text: String): SendKind? = if (text.isEmpty()) null else sendPhrases[normalized(text)]

    /** True when the WHOLE utterance asks for the Enter or Send key. */
    fun isSendCommand(text: String): Boolean = sendCommand(text) != null

    private val trailingSendRegex = Regex(
        "^(.+?)\\s*([,.;:!?])\\s*(" + alternatives(sendPhrases.keys) + ")\\s*[.!?]*$",
        RegexOption.IGNORE_CASE,
    )

    /**
     * "how are you? send it" as ("how are you?", SEND): the command at the end of the same
     * sentence, said in one go. It needs a pause before it (a comma, full stop or question
     * mark), so "please send it to Sam" stays ordinary dictation. Null when there is no such ending.
     */
    fun splitTrailingSend(text: String): Pair<String, SendKind>? {
        val match = trailingSendRegex.matchEntire(text.trim()) ?: return null
        val sentence = match.groupValues[1].trim()
        val kind = sendPhrases[match.groupValues[3].lowercase()] ?: return null
        if (sentence.isEmpty()) return null
        val mark = match.groupValues[2]
        return (if (mark == "?" || mark == "!") sentence + mark else sentence) to kind
    }

    /** What is left of [text] after the edit, and how many characters were removed. */
    data class Deletion(val remaining: String, val removed: Int)

    fun computeDeletion(text: String, edit: Edit): Deletion {
        if (edit == Edit.ALL || text.isEmpty()) return Deletion("", text.length)
        return when (edit) {
            Edit.WORD -> {
                val stripped = text.trimEnd()
                val index = stripped.lastIndexOf(' ')
                if (index == -1) Deletion("", text.length)
                else Deletion(stripped.substring(0, index), text.length - index)
            }
            Edit.SENTENCE -> {
                val searchArea = text.dropLast(1) // a terminator at the very end is not a boundary
                val index = maxOf(
                    searchArea.lastIndexOf('.'),
                    searchArea.lastIndexOf('!'),
                    searchArea.lastIndexOf('?'),
                )
                if (index == -1) Deletion("", text.length)
                else Deletion(text.substring(0, index + 1), text.length - (index + 1))
            }
            Edit.ALL -> Deletion("", text.length)
        }
    }
}
