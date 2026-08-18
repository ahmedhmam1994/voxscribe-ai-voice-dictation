package com.voxscribe.android

/**
 * Rule-based transcript cleanup -- a direct Kotlin port of the desktop
 * VoxScribe app's `core/cleanup.py`. Deliberately NOT an LLM/API call: no
 * per-request cost, works fully offline, runs in microseconds. It's a
 * handful of well-known filler-word/spacing patterns, not a real NLP
 * pipeline -- keep expectations in line with the Python original.
 *
 * Keep this in sync with core/cleanup.py in the desktop project if that
 * file's rules change.
 */
object TranscriptCleanup {

    // Filler words safe to strip as whole words wherever they occur -- they
    // never form part of a legitimate sentence on their own.
    private val simpleFillerRegex = Regex(
        "\\b(?:um|uh|uhh|umm)\\b[,]?",
        RegexOption.IGNORE_CASE
    )

    private val youKnowRegex = Regex("\\byou know\\b[,]?", RegexOption.IGNORE_CASE)

    // "like" is unsafe to strip everywhere -- "I like pizza" needs its "like".
    // Only stripped when comma-bounded (clear filler/hedge usage).
    private val likeMidSentenceRegex = Regex(",\\s*like\\s*,", RegexOption.IGNORE_CASE)

    private val likeLeadWords = listOf("so", "and", "but", "well", "ok", "okay")
    private val likeLeadingRegex = Regex(
        "(^|[.!?]\\s+)((?:${likeLeadWords.joinToString("|")})\\s+)?like\\s*,\\s*",
        RegexOption.IGNORE_CASE
    )

    // Collapse an immediately-repeated word ("the the", "I I") into one,
    // keeping the first occurrence's casing.
    private val repeatedWordRegex = Regex("\\b(\\w+)\\b(\\s+\\1\\b)+", RegexOption.IGNORE_CASE)

    private val spaceBeforePunctRegex = Regex("\\s+([,.!?;:])")
    private val multiSpaceRegex = Regex("\\s+")
    private val leadingStrayPunctRegex = Regex("^[,;:]\\s*")

    /** Strip common filler words/phrases and fix up spacing/capitalization. */
    fun clean(text: String): String {
        if (text.isBlank()) return text

        var result = text

        // Filler phrases first, before the repeated-word/spacing passes clean
        // up whatever gaps they leave behind.
        result = likeMidSentenceRegex.replace(result, ",")
        result = likeLeadingRegex.replace(result) { m -> (m.groupValues[1] + m.groupValues[2]) }
        result = youKnowRegex.replace(result, "")
        result = simpleFillerRegex.replace(result, "")

        // Collapse immediately-repeated words produced by dictation stutter.
        result = repeatedWordRegex.replace(result) { m -> m.groupValues[1] }

        // Spacing cleanup.
        result = spaceBeforePunctRegex.replace(result) { m -> m.groupValues[1] }
        result = multiSpaceRegex.replace(result, " ").trim()

        // Stray leading punctuation left over from a stripped filler at the
        // very start of the text (e.g. "um, so..." -> ", so..." -> "so...").
        result = leadingStrayPunctRegex.replace(result, "")

        // Capitalize the first letter of the result.
        if (result.isNotEmpty()) {
            result = result[0].uppercaseChar() + result.substring(1)
        }

        return result
    }
}
