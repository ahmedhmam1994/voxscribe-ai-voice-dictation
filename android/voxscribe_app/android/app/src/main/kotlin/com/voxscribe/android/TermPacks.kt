package com.voxscribe.android

import kotlin.math.abs
import kotlin.math.min

/**
 * Term packs: ready-made word lists for a field (medical, law, business) and
 * the user's own list files, plus the pass that fixes how those words are
 * written. A port of the Windows app's core/term_packs.py; the pack files are
 * the same ones, bundled under assets/packs. Everything is local.
 *
 * The correction pass works with every speech model: it fixes the casing of a
 * listed word ("mri" to "MRI"), joins a word the model split in two ("met
 * formin" to "metformin") and, for the rare words a pack marks as safe for it
 * (drug names), repairs a misspelling or a same-sounding spelling ("lisinipril"
 * to "lisinopril"). Ordinary words are never repaired that way, since
 * "expression" is one slip from "depression".
 *
 * A pack file may hold the line "# fuzzy: on" before such rare terms and
 * "# fuzzy: off" after them. Without those lines a term only gets its casing fixed.
 */
object TermPacks {

    /** (id, label) of the packs that ship with the app, in the order they are shown. */
    val BUILTIN = listOf("medical" to "Medical", "legal" to "Law", "business" to "Business")
    const val USER_PREFIX = "user:"

    const val MAX_TERMS = 6000
    const val MAX_TERM_LENGTH = 60
    const val MAX_FILE_BYTES = 1_000_000
    private const val MAX_PHRASE_WORDS = 4
    private const val MIN_JOINED = 7
    private const val MIN_FUZZY = 8
    private const val LONG = 9
    private const val FUZZY_RATIO = 0.9
    private const val ANCHOR_RATIO = 0.84
    private const val GAP_RATIO = 0.88
    private const val SWAP_COST = 0.5
    private const val SOUND_DISTANCE = 1.6
    private const val MARGIN = 0.3

    private val token = Regex("[A-Za-z0-9]+(?:['’\\-][A-Za-z0-9]+)*")
    private val spaces = Regex("\\s+")
    private val BOM = Char(0xFEFF)

    /** The terms in a pack file, and the ones among them that may be repaired when misspelled. */
    data class Pack(val terms: List<String>, val fuzzy: List<String>)

    /** No blanks, notes or repeats (any case). The fuzzy terms sit between "# fuzzy: on" and "# fuzzy: off". */
    fun parse(text: String): Pack {
        val terms = mutableListOf<String>()
        val fuzzy = mutableListOf<String>()
        val seen = HashSet<String>()
        var fuzzyOn = false
        for (line in text.trimStart(BOM).lines()) {
            val term = line.trim().split(spaces).filter { it.isNotEmpty() }.joinToString(" ")
            val lower = term.lowercase()
            if (lower == "# fuzzy: on" || lower == "# fuzzy: off") {
                fuzzyOn = lower.endsWith("on")
                continue
            }
            if (term.isEmpty() || term.startsWith("#") || term.length > MAX_TERM_LENGTH) continue
            if (!seen.add(lower)) continue
            terms += term
            if (fuzzyOn) fuzzy += term
            if (terms.size >= MAX_TERMS) break
        }
        return Pack(terms, fuzzy)
    }

    /** Each pack's terms in order, no repeats. */
    fun combinedTerms(packs: List<Pack>): List<String> {
        val seen = HashSet<String>()
        return packs.flatMap { it.terms }.filter { seen.add(it.lowercase()) }.take(MAX_TERMS)
    }

    fun combinedFuzzy(packs: List<Pack>): List<String> = packs.flatMap { it.fuzzy }

    // -- how close a heard word is to a listed one ---------------------------------

    private val softPairs = listOf("aeiou", "bp", "dt", "gk", "sz", "fv", "ck", "cs")
    private const val VOWELS = "aeiou"

    fun soft(a: Char, b: Char): Boolean = softPairs.any { a in it && b in it }

    private fun substitutionCost(a: Char, b: Char): Double = when {
        a == b -> 0.0
        a in VOWELS && b in VOWELS -> 0.25
        soft(a, b) -> 0.4
        else -> 1.0
    }

    private fun gapCost(ch: Char): Double = if (ch in VOWELS) 0.6 else 1.0

    /**
     * Edit distance in which look-alike sounds (vowel for vowel, b/p, d/t, g/k,
     * s/z, f/v), a missing vowel and two neighbouring letters swapped cost little.
     * "lezenobril" is 1.6 from "lisinopril", while "permission" is far from "percussion".
     */
    fun soundDistance(a: String, b: String): Double {
        val rows = Array(a.length + 1) { DoubleArray(b.length + 1) }
        for (j in 1..b.length) rows[0][j] = rows[0][j - 1] + gapCost(b[j - 1])
        for (i in 1..a.length) {
            val chA = a[i - 1]
            rows[i][0] = rows[i - 1][0] + gapCost(chA)
            for (j in 1..b.length) {
                val chB = b[j - 1]
                var best = minOf(
                    rows[i - 1][j - 1] + substitutionCost(chA, chB),
                    rows[i - 1][j] + gapCost(chA),
                    rows[i][j - 1] + gapCost(chB),
                )
                if (i > 1 && j > 1 && chA == b[j - 2] && a[i - 2] == chB) {
                    best = min(best, rows[i - 2][j - 2] + SWAP_COST)
                }
                rows[i][j] = best
            }
        }
        return rows[a.length][b.length]
    }

    /** How far [word] is from [term] when it is a clear mishearing of it (lower is closer), else null. Both lowercase. */
    private fun closeness(word: String, term: String): Double? {
        val gap = abs(word.length - term.length)
        if (gap > 2 || !(word[0] == term[0] || soft(word[0], term[0]))) return null
        val ratio = SequenceMatcher.ratio(word, term)
        if (gap == 2) {
            // A syllable dropped ("amoxillin"): only for long words that start alike.
            if (word.length < LONG - 1 || word.take(4) != term.take(4) || ratio < GAP_RATIO) return null
            return 2.0 * (1.0 - ratio) * term.length
        }
        val distance = soundDistance(word, term)
        val anchored = word.length >= LONG &&
            word.take(3) == term.take(3) &&
            word.takeLast(3) == term.takeLast(3) &&
            ratio >= ANCHOR_RATIO
        if (ratio >= FUZZY_RATIO || distance <= SOUND_DISTANCE || anchored) {
            return min(distance, 2.0 * (1.0 - ratio) * term.length)
        }
        return null
    }

    private fun String.isAlpha(): Boolean = isNotEmpty() && all { it.isLetter() }

    /** Python's str.islower(): some letter, and no capital. */
    private fun String.isLowerCased(): Boolean = any { it.isLetter() } && none { it.isUpperCase() }

    private class Index(terms: List<String>, fuzzyTerms: List<String>) {
        val single = HashMap<String, String>()
        val phrase = HashMap<String, String>()
        val fuzzy = LinkedHashMap<String, String>()
        val acronyms = HashMap<String, String>()
        var maxWords = 1

        init {
            for (term in terms) {
                val words = term.split(" ")
                if (words.size == 1) {
                    single.putIfAbsent(term.lowercase(), term)
                    if (term.isAlpha() && term.all { it.isUpperCase() } && term.length >= 2) {
                        acronyms.putIfAbsent(term.lowercase(), term)
                    }
                    if ('-' in term) {
                        // "X ray" and "xray" for "X-ray": a model drops the hyphen.
                        phrase.putIfAbsent(term.lowercase().replace("-", " "), term)
                        maxWords = maxOf(maxWords, term.count { it == '-' } + 1)
                    }
                } else if (words.size <= MAX_PHRASE_WORDS) {
                    phrase.putIfAbsent(term.lowercase(), term)
                    maxWords = maxOf(maxWords, words.size)
                }
            }
            for (term in fuzzyTerms) {
                if (term.isAlpha() && term.length >= MIN_FUZZY) fuzzy.putIfAbsent(term.lowercase(), term)
            }
        }

        /** A fuzzy-safe listed word that [token] is a clear mishearing of. */
        fun near(token: String): String? {
            val lower = token.lowercase()
            if (!token.isAlpha() || lower.length < MIN_FUZZY || lower in single) return null
            val scored = fuzzy.mapNotNull { (candidateLower, candidate) ->
                closeness(lower, candidateLower)?.let { it to candidate }
            }.sortedWith(compareBy({ it.first }, { it.second }))
            if (scored.isEmpty()) return null
            // Two listed words equally close means a guess: leave the text alone.
            if (scored.size > 1 && scored[1].first - scored[0].first < MARGIN) return null
            return scored[0].second
        }
    }

    private var cachedKey: Pair<List<String>, List<String>>? = null
    private var cachedIndex: Index? = null

    @Synchronized
    private fun index(terms: List<String>, fuzzy: List<String>): Index {
        val key = terms to fuzzy
        cachedIndex?.let { if (cachedKey == key) return it }
        return Index(terms, fuzzy).also {
            cachedKey = key
            cachedIndex = it
        }
    }

    /** A lowercase term keeps a capital only at the start of a sentence. */
    private fun like(original: String, canonical: String, text: String, start: Int): String {
        val before = text.substring(0, start).trimEnd(' ', '\t')
        val atSentenceStart = before.isEmpty() || before.last() in ".!?\n"
        if (canonical.isLowerCased() && original.take(1).let { it.isNotEmpty() && it[0].isUpperCase() } && atSentenceStart) {
            return canonical.replaceFirstChar { it.uppercaseChar() }
        }
        return canonical
    }

    /** Rewrites the words of [text] that match a listed term. Text without Latin letters is left alone. */
    fun correct(text: String, terms: List<String>, fuzzyTerms: List<String> = emptyList()): String {
        if (terms.isEmpty() || text.isEmpty()) return text
        val index = index(terms, fuzzyTerms)
        val tokens = token.findAll(text).toList()
        val out = StringBuilder()
        var cursor = 0
        var i = 0
        while (i < tokens.size) {
            var replaced = false
            val longest = minOf(maxOf(index.maxWords, 3), tokens.size - i)
            for (size in longest downTo 1) {
                val window = tokens.subList(i, i + size)
                val spaced = window.zipWithNext().all { (a, b) -> text.substring(a.range.last + 1, b.range.first) == " " }
                if (!spaced) continue
                val start = window.first().range.first
                val end = window.last().range.last + 1
                val original = text.substring(start, end)
                val lowerWords = window.map { it.value.lowercase() }
                var canonical: String? = null
                if (size >= 2) {
                    canonical = index.phrase[lowerWords.joinToString(" ")]
                    if (canonical == null && lowerWords.all { it.length == 1 }) {
                        // Letters spelled out ("C A C") for a listed acronym.
                        canonical = index.acronyms[lowerWords.joinToString("")]
                    }
                    if (canonical == null && size <= 3) {
                        val joined = lowerWords.joinToString("")
                        if (joined.length >= MIN_JOINED) canonical = index.single[joined]
                    }
                } else {
                    canonical = index.single[lowerWords[0]] ?: index.near(original)
                }
                if (canonical == null) continue
                val fixed = like(original, canonical, text, start)
                if (fixed != original) {
                    out.append(text, cursor, start)
                    out.append(fixed)
                    cursor = end
                }
                i += size
                replaced = true
                break
            }
            if (!replaced) i += 1
        }
        out.append(text, cursor, text.length)
        return out.toString()
    }
}
