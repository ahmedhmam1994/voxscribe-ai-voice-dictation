package com.voxscribe.android

/**
 * Smart formatting, a Pro feature: spoken emails, web addresses and numbers
 * typed the way they are written. A port of the Windows app's rules, no model
 * and no network.
 *
 *   "john dot smith at gmail dot com"   gives john.smith@gmail.com
 *   "example dot com slash pricing"     gives example.com/pricing
 *   "twenty five percent"               gives 25%
 *   "one hundred and five dollars"      gives $105
 *   "five five five one two three four" gives 5551234
 *
 * Conservative on purpose: a lone small number ("one of them") stays a word,
 * and a number phrase that does not parse cleanly is left untouched.
 */
object SmartFormat {

    private val ones = linkedMapOf(
        "zero" to 0, "one" to 1, "two" to 2, "three" to 3, "four" to 4, "five" to 5, "six" to 6,
        "seven" to 7, "eight" to 8, "nine" to 9, "ten" to 10, "eleven" to 11, "twelve" to 12,
        "thirteen" to 13, "fourteen" to 14, "fifteen" to 15, "sixteen" to 16, "seventeen" to 17,
        "eighteen" to 18, "nineteen" to 19,
    )
    private val tens = linkedMapOf(
        "twenty" to 20, "thirty" to 30, "forty" to 40, "fifty" to 50,
        "sixty" to 60, "seventy" to 70, "eighty" to 80, "ninety" to 90,
    )
    private val scales = linkedMapOf("hundred" to 100, "thousand" to 1_000, "million" to 1_000_000)
    private val digits = ones.filterValues { it < 10 }

    private val numberWord = (ones.keys + tens.keys + scales.keys).joinToString("|")
    private val digitWord = digits.keys.joinToString("|")
    private val run = "(?:$numberWord)(?:[\\s-]+(?:and[\\s-]+)?(?:$numberWord))*"
    private val numberRe = Regex(
        "\\b(?<whole>$run)(?:\\s+point\\s+(?<decimals>(?:$digitWord)(?:\\s+(?:$digitWord))*))?" +
            "(?:\\s+(?<unit>percent|dollars?|euros?))?\\b",
        RegexOption.IGNORE_CASE,
    )
    private val phoneRe = Regex(
        "\\b(?:(?:$digitWord|oh)(?:[\\s,-]+|\\b)){7,}",
        RegexOption.IGNORE_CASE,
    )

    private const val TLDS = "com|org|net|io|co|edu|gov|app|dev|ai|me|info|uk|de|fr"
    private const val PART = "[a-z0-9]+"
    private const val LOCAL = "$PART(?:\\s+(?:dot|underscore|dash)\\s+$PART)*"
    private const val DOMAIN = "$PART(?:\\s+(?:dot|dash)\\s+$PART)*\\s+dot\\s+(?:$TLDS)"
    private val emailRe = Regex("\\b(?<local>$LOCAL)\\s+at\\s+(?<domain>$DOMAIN)\\b", RegexOption.IGNORE_CASE)
    private val urlRe = Regex(
        "\\b(?<scheme>https?\\s+colon\\s+slash\\s+slash\\s+)?(?<host>(?:w\\s+w\\s+w\\s+dot\\s+)?$DOMAIN)" +
            "(?<path>(?:\\s+slash\\s+$PART(?:\\s+(?:dash|dot|underscore)\\s+$PART)*)*)\\b",
        RegexOption.IGNORE_CASE,
    )

    /** Ordinary words before "at" ("look at example dot com") that are not an email's start. */
    private val notALocalPart = setOf(
        "look", "looking", "meet", "meeting", "here", "there", "arrive", "arrived", "good",
        "glad", "stay", "stop", "start", "starting", "aimed", "stare", "smile", "laugh",
        "work", "working", "available", "ready", "come", "go", "sit", "stand", "wait",
        "back", "out", "up", "down", "once", "least", "most", "all", "what", "who",
    )

    private val spokenSymbols = mapOf("dot" to ".", "underscore" to "_", "dash" to "-", "slash" to "/")

    private fun joinSpoken(words: String): String =
        words.lowercase().split(Regex("\\s+")).filter { it.isNotEmpty() }
            .joinToString("") { spokenSymbols[it] ?: it }

    private fun email(match: MatchResult): String {
        val local = match.groups["local"]!!.value
        val parts = local.split(Regex("\\s+")).filter { it.isNotEmpty() }
        if (parts.first().lowercase() in notALocalPart && parts.size == 1) return match.value
        return "${joinSpoken(local)}@${joinSpoken(match.groups["domain"]!!.value)}"
    }

    private fun url(match: MatchResult): String {
        val spokenScheme = (match.groups["scheme"]?.value ?: "").lowercase()
        val scheme = when {
            "https" in spokenScheme -> "https://"
            spokenScheme.isNotEmpty() -> "http://"
            else -> ""
        }
        val spokenHost = match.groups["host"]!!.value
        var host = joinSpoken(spokenHost).removePrefix("www.")
        if (spokenHost.lowercase().startsWith("w w w")) host = "www.$host"
        return "$scheme$host${joinSpoken(match.groups["path"]?.value ?: "")}"
    }

    private fun phone(match: MatchResult): String {
        val out = StringBuilder()
        for (word in Regex("[a-z]+").findAll(match.value.lowercase())) {
            out.append(if (word.value == "oh") "0" else digits.getValue(word.value).toString())
        }
        if (match.value.endsWith(" ") || match.value.endsWith(",") || match.value.endsWith("-")) out.append(' ')
        return out.toString()
    }

    /** "one hundred and five" gives 105, or null when the words are not a clean number. */
    fun parseNumberWords(phrase: String): Int? {
        var total = 0
        var current = 0
        var previous = "" // "ones", "teens", "tens" or "scale"
        for (word in phrase.lowercase().split(Regex("[\\s-]+"))) {
            if (word == "and") continue
            when {
                word in scales -> {
                    val scale = scales.getValue(word)
                    if (scale == 100) {
                        current = maxOf(current, 1) * 100
                    } else {
                        total += maxOf(current, 1) * scale
                        current = 0
                    }
                    previous = "scale"
                }
                word in tens -> {
                    if (previous in setOf("ones", "teens", "tens")) return null
                    current += tens.getValue(word)
                    previous = "tens"
                }
                word in ones -> {
                    val value = ones.getValue(word)
                    if (previous in setOf("ones", "teens") || (previous == "tens" && value >= 10)) return null
                    current += value
                    previous = if (value < 10) "ones" else "teens"
                }
                else -> return null
            }
        }
        return total + current
    }

    private fun number(match: MatchResult): String {
        val value = parseNumberWords(match.groups["whole"]!!.value) ?: return match.value
        val decimals = match.groups["decimals"]?.value
        val unit = (match.groups["unit"]?.value ?: "").lowercase()
        val text = if (decimals != null) {
            "$value." + decimals.lowercase().split(Regex("\\s+")).joinToString("") { digits.getValue(it).toString() }
        } else {
            value.toString()
        }
        return when {
            unit == "percent" -> "$text%"
            unit.startsWith("dollar") -> "$$text"
            unit.startsWith("euro") -> "€$text"
            value < 10 && decimals == null -> match.value // a lone small number reads better as a word
            else -> text
        }
    }

    /** Rewrites spoken emails, web addresses and numbers. Other text is unchanged. */
    fun format(text: String): String {
        if (text.isEmpty()) return text
        var result = emailRe.replace(text) { email(it) }
        result = urlRe.replace(result) { url(it) }
        result = phoneRe.replace(result) { phone(it) }
        return numberRe.replace(result) { number(it) }
    }
}
