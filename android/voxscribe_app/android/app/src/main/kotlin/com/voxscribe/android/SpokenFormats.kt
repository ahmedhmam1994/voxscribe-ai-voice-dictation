package com.voxscribe.android

import java.util.Locale

/**
 * Spoken formats: numbers, doses and references typed the way a professional
 * writes them, following the term packs that are switched on. A port of the
 * Windows app's core/spoken_formats.py.
 *
 *   Medical   "one twenty over eighty"            gives 120/80
 *             "five milligrams twice daily"       gives 5 mg BID
 *             "ten milligrams every eight hours"  gives 10 mg q8h
 *   Law       "section twelve subsection b"       gives section 12(b)
 *             "Smith versus Jones"                gives Smith v. Jones
 *   Business  "fifty thousand dollars"            gives $50,000
 *             "q three"                           gives Q3
 *
 * Rules only, and deliberately narrow: a number is only rewritten next to the
 * unit or keyword that shows what it is, so "one of them" stays a word. Off by
 * default.
 */
object SpokenFormats {

    private val words = (SmartFormat.ones.keys + SmartFormat.tens.keys + listOf("hundred", "thousand")).joinToString("|")

    // "and" only joins after hundred or thousand ("one hundred and five"), never two separate numbers.
    private val run = """(?:a\s+)?(?:$words)(?:[\s-]+(?:$words)|(?:(?<=hundred)|(?<=thousand))\s+and\s+(?:$words))*"""

    // Speech models often write the digits themselves ("5 milligrams"), so every rule takes digits too.
    private val amount = """(?:\d+(?:,\d{3})*(?:\.\d+)?|$run)"""
    private val digitWords = (listOf("oh") + SmartFormat.digits.keys).joinToString("|")
    private val digitSeq = """(?:$digitWords)(?:\s+(?:$digitWords))*"""
    private val hundredsDigits = SmartFormat.digits.filterValues { it in 1..9 }
    private val plainDigits = Regex("""\d+""")
    private val writtenNumber = Regex("""\d+(?:,\d{3})*(?:\.\d+)?""")
    private val wordSplit = Regex("""[\s-]+""")
    private val ic = RegexOption.IGNORE_CASE

    /** "one hundred and five" is 105, "one twenty" is 120 (as blood pressure is said), "a hundred" is 100. */
    fun spokenInt(phrase: String): Int? {
        val cleaned = phrase.trim().replace(",", "")
        if (plainDigits.matches(cleaned)) return cleaned.toIntOrNull()
        val parts = phrase.lowercase().trim().split(wordSplit).toMutableList()
        if (parts.firstOrNull() == "a") parts[0] = "one"
        SmartFormat.parseNumberWords(parts.joinToString(" "))?.let { return it }
        if (parts.size >= 2) {
            val hundreds = hundredsDigits[parts[0]]
            val rest = SmartFormat.parseNumberWords(parts.drop(1).joinToString(" "))
            if (hundreds != null && rest != null && rest in 10..99) return hundreds * 100 + rest
        }
        return null
    }

    private fun decimals(spoken: String?): String {
        if (spoken.isNullOrEmpty()) return ""
        return "." + spoken.lowercase().split(Regex("\\s+")).joinToString("") {
            if (it == "oh") "0" else SmartFormat.digits.getValue(it).toString()
        }
    }

    /** "five" gives "5", "two" and "five" give "2.5"; null when the words are not a number. */
    private fun number(whole: String?, decimalWords: String?): String? {
        if (whole != null && writtenNumber.matches(whole.trim())) {
            return if (decimalWords != null) null else whole.trim().replace(",", "")
        }
        var value = 0
        if (whole != null) {
            value = spokenInt(whole) ?: return null
        } else if (decimalWords == null) {
            return null
        }
        return "$value${decimals(decimalWords)}"
    }

    private fun MatchResult.group(name: String): String? = groups[name]?.value

    // -- medical ---------------------------------------------------------------------

    private val misheardPressure = Regex("""(?<![\w-])(?:on|one|won)\s+(?<tens>\d{2})\s+over\s+(?<dia>\d{2,3})\b""", ic)
    private val bloodPressure = Regex("""(?<![\w-])(?<sys>$amount)\s+over\s+(?<dia>$amount)\b""", ic)

    private fun plausiblePressure(systolic: Int, diastolic: Int) =
        systolic in 60..300 && diastolic in 30..200 && diastolic < systolic

    private fun bloodPressure(match: MatchResult): String {
        val systolic = spokenInt(match.group("sys")!!) ?: return match.value
        val diastolic = spokenInt(match.group("dia")!!) ?: return match.value
        return if (plausiblePressure(systolic, diastolic)) "$systolic/$diastolic" else match.value
    }

    /** "one twenty over eighty" is often written "on 20 over 80". */
    private fun misheardPressure(match: MatchResult): String {
        val systolic = 100 + match.group("tens")!!.toInt()
        val diastolic = match.group("dia")!!.toInt()
        return if (plausiblePressure(systolic, diastolic)) "$systolic/$diastolic" else match.value
    }

    private val units = mapOf(
        "milligram" to "mg", "microgram" to "mcg", "milliliter" to "mL", "millilitre" to "mL",
        "gram" to "g", "kilogram" to "kg", "milliequivalent" to "mEq",
    )
    private val dose = Regex(
        """(?<![\w-])(?:(?<whole>$amount)(?:\s+point\s+(?<dec>$digitSeq))?|point\s+(?<dec2>$digitSeq))""" +
            """\s+(?<unit>milligrams?|micrograms?|milliliters?|millilitres?|grams?|kilograms?|milliequivalents?)\b""",
        ic,
    )

    private fun dose(match: MatchResult): String {
        val value = number(match.group("whole"), match.group("dec") ?: match.group("dec2")) ?: return match.value
        val unit = match.group("unit")!!.lowercase().trimEnd('s')
        return "$value ${units.getValue(unit)}"
    }

    private val afterDose = Regex(
        """(?<dose>\b\d[\d.]*\s(?:mg|mcg|mL|g|kg|mEq))""" +
            """(?<tail>(?:\s+(?:by\s+mouth|twice\s+(?:a\s+day|daily)|three\s+times\s+(?:a\s+day|daily)""" +
            """|four\s+times\s+(?:a\s+day|daily)|every\s+(?:$amount)\s+hours?|as\s+needed))+)""",
        ic,
    )
    private val tailParts = listOf(
        Regex("""\bby\s+mouth\b""", ic) to "PO",
        Regex("""\btwice\s+(?:a\s+day|daily)\b""", ic) to "BID",
        Regex("""\bthree\s+times\s+(?:a\s+day|daily)\b""", ic) to "TID",
        Regex("""\bfour\s+times\s+(?:a\s+day|daily)\b""", ic) to "QID",
        Regex("""\bas\s+needed\b""", ic) to "PRN",
    )
    private val everyHours = Regex("""\bevery\s+(?<n>$amount)\s+hours?\b""", ic)

    private fun afterDose(match: MatchResult): String {
        var tail = match.group("tail")!!
        for ((pattern, short) in tailParts) tail = pattern.replace(tail, short)
        tail = everyHours.replace(tail) { m ->
            val hours = spokenInt(m.group("n")!!)
            if (hours != null && hours in 1..48) "q${hours}h" else m.value
        }
        return match.group("dose")!! + tail
    }

    // -- percent (medical and business) ---------------------------------------------

    private val percent = Regex("""(?<![\w-])(?<whole>$amount)(?:\s+point\s+(?<dec>$digitSeq))?\s+percent\b""", ic)

    // -- law ---------------------------------------------------------------------------

    private const val SUB_KEYWORD = """(?:subsection|sub\s+section|subparagraph|sub\s+paragraph|paragraph|subclause)"""
    private val reference = Regex(
        """\b(?<kw>section|clause|article|paragraph|chapter|rule|schedule|exhibit|appendix)""" +
            """\s+(?<num>$amount)(?:\s+point\s+(?<dec>$digitSeq))?""" +
            """(?<subs>(?:\s+$SUB_KEYWORD\s+(?:[a-z]\b|$amount))*)""",
        ic,
    )
    private val subPart = Regex("""$SUB_KEYWORD\s+(?<part>[a-z]\b|$amount)""", ic)

    private fun reference(match: MatchResult): String {
        val value = number(match.group("num"), match.group("dec")) ?: return match.value
        val subs = StringBuilder()
        for (part in subPart.findAll(match.group("subs").orEmpty())) {
            val text = part.group("part")!!
            val shown: Any = if (text.length == 1) text.lowercase() else (spokenInt(text) ?: return match.value)
            subs.append("(").append(shown).append(")")
        }
        return "${match.group("kw")} $value$subs"
    }

    private val versus = Regex("""\b([A-Z][\w'’-]+)\s+(?:versus|vs\.?)\s+(?=[A-Z])""")

    // -- business ------------------------------------------------------------------------

    private val money = Regex(
        """(?<![\w-])(?<whole>$amount)(?:\s+point\s+(?<dec>$digitSeq))?""" +
            """(?:\s+(?<big>million|billion|trillion))?\s+(?<cur>dollars|euros)\b""",
        ic,
    )
    private val symbols = mapOf("dollars" to "$", "euros" to "€")

    private fun money(match: MatchResult): String {
        val value = number(match.group("whole"), match.group("dec")) ?: return match.value
        val symbol = symbols.getValue(match.group("cur")!!.lowercase())
        val big = match.group("big")?.lowercase().orEmpty()
        if (big.isNotEmpty()) return "$symbol$value $big"
        val whole = value.substringBefore('.')
        val fraction = if ('.' in value) "." + value.substringAfter('.') else ""
        val grouped = whole.toLongOrNull()?.let { String.format(Locale.US, "%,d", it) } ?: whole
        return "$symbol$grouped$fraction"
    }

    private val quarter = Regex("""\bq\s*(one|two|three|four)\b""", ic)
    private val quarterNumber = mapOf("one" to 1, "two" to 2, "three" to 3, "four" to 4)

    /** Rewrites the spoken numbers that the switched on [packs] call for. */
    fun apply(text: String, packs: List<String>): String {
        if (text.isEmpty() || packs.isEmpty()) return text
        var result = text
        if ("medical" in packs) {
            result = misheardPressure.replace(result) { misheardPressure(it) }
            result = bloodPressure.replace(result) { bloodPressure(it) }
            result = dose.replace(result) { dose(it) }
            result = afterDose.replace(result) { afterDose(it) }
        }
        if ("medical" in packs || "business" in packs) {
            result = percent.replace(result) { m -> number(m.group("whole"), m.group("dec"))?.let { "$it%" } ?: m.value }
        }
        if ("legal" in packs) {
            result = reference.replace(result) { reference(it) }
            result = versus.replace(result) { "${it.groupValues[1]} v. " }
        }
        if ("business" in packs) {
            result = money.replace(result) { money(it) }
            result = quarter.replace(result) { "Q${quarterNumber.getValue(it.groupValues[1].lowercase())}" }
        }
        return result
    }
}
