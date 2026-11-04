package com.voxscribe.android

import android.content.Context
import android.util.Base64
import kotlin.math.abs

/**
 * Screen-aware spelling: the names and special words on screen when you
 * dictate (the person in the chat, a contact, a product) fix how the speech
 * model wrote them. "whatsapp" becomes "WhatsApp", "vox scribe" becomes
 * "VoxScribe", and "Muhammad" becomes "Mohammed" when the screen spells it
 * that way.
 *
 * Only words that look like names are taken from the screen: a capital at the
 * start, capitals inside ("iPhone"), a short acronym, or letters with digits.
 * A common word never counts, so a button that says "Join" cannot turn "John"
 * into "Join", and an ordinary capitalized word is only fixed in what you said
 * when the model also wrote it as a name. The screen is read on the phone at
 * the moment you dictate and is kept nowhere.
 */
object ScreenWords {

    const val MAX_TERMS = 300
    private const val MIN_LENGTH = 3
    private const val MAX_ACRONYM = 5
    private const val MIN_FUZZY = 4
    private const val SHORT = 6
    private const val SHORT_DISTANCE = 1.0
    private const val LONG_DISTANCE = 1.6
    private const val MIN_JOINED = 6
    private const val MARGIN = 0.3

    private val word = Regex("[\\p{L}\\p{M}\\p{Nd}]+")
    private val suffixes = listOf("s", "es", "ed", "ing", "er", "ers", "ly", "ies", "ied")

    /** True for "iPhone", "VoxScribe", "NASA", "B12": a word nobody writes that way by accident. */
    private fun isSpecial(term: String): Boolean =
        term.drop(1).any { it.isUpperCase() } || (term.any { it.isDigit() } && term.any { it.isLetter() })

    /** [lower] or a plain form of it ("archived", "dictating") is one of the [common] words. */
    fun isCommon(lower: String, common: Set<String>): Boolean {
        if (lower in common) return true
        for (suffix in suffixes) {
            if (!lower.endsWith(suffix) || lower.length - suffix.length < 3) continue
            val stem = lower.dropLast(suffix.length)
            if (stem in common || stem + "e" in common) return true
            if (suffix.startsWith("i") && stem + "y" in common) return true
            // "running" to "run".
            if (stem.length >= 3 && stem.last() == stem[stem.length - 2] && stem.dropLast(1) in common) return true
        }
        return false
    }

    /**
     * The words in [texts] (what the screen shows) that may fix spelling, most
     * shown first. A word the screen also writes in lower case is left out:
     * there it is an ordinary word, not a name.
     */
    fun terms(texts: List<String>, common: Set<String>): List<String> {
        if (common.isEmpty()) return emptyList()
        val counts = HashMap<String, Int>()
        val order = ArrayList<String>()
        val lowerSeen = HashSet<String>()
        for (text in texts) {
            for (match in word.findAll(text)) {
                val w = match.value
                if (w.none { it.isLetter() }) continue
                val lower = w.lowercase()
                if (w.none { it.isUpperCase() }) {
                    lowerSeen += lower
                    continue
                }
                if (w.length < MIN_LENGTH || isCommon(lower, common)) continue
                // Long all-capital words are shouted labels ("SUBTOTAL"), not acronyms.
                if (w.length > MAX_ACRONYM && w.none { it.isLowerCase() }) continue
                if (w !in counts) order += w
                counts[w] = (counts[w] ?: 0) + 1
            }
        }
        val best = LinkedHashMap<String, String>()
        for (w in order.sortedByDescending { counts[it] }) {
            val lower = w.lowercase()
            if (lower !in lowerSeen) best.putIfAbsent(lower, w)
        }
        return best.values.take(MAX_TERMS)
    }

    /** The closest name in [names] that [heard] is a clear mishearing of, or null when none or two are as close. */
    private fun near(heard: String, names: List<String>, common: Set<String>): String? {
        val lower = heard.lowercase()
        if (lower.length < MIN_FUZZY || !heard.all { it.isLetter() } || isCommon(lower, common)) return null
        val scored = names.mapNotNull { name ->
            val target = name.lowercase()
            if (target.length < MIN_FUZZY || abs(target.length - lower.length) > 2) return@mapNotNull null
            val short = target.length < SHORT
            // A short name must start with the same letter: "Kevin" is not "Gavin".
            val sameStart = target[0] == lower[0] || (!short && TermPacks.soft(target[0], lower[0]))
            if (!sameStart) return@mapNotNull null
            val distance = TermPacks.soundDistance(lower, target)
            if (distance > (if (short) SHORT_DISTANCE else LONG_DISTANCE)) null else distance to name
        }.sortedWith(compareBy({ it.first }, { it.second }))
        if (scored.isEmpty()) return null
        if (scored.size > 1 && scored[1].first - scored[0].first < MARGIN) return null
        return scored[0].second
    }

    /** Rewrites the words of [text] that are the screen's [terms] written another way. */
    fun correct(text: String, terms: List<String>, common: Set<String>): String {
        if (terms.isEmpty() || text.isEmpty() || common.isEmpty()) return text
        val special = terms.filter { isSpecial(it) || it.none { ch -> ch.isLowerCase() } }
            .associateBy { it.lowercase() }
        val names = terms.filter { it.lowercase() !in special && it.all { ch -> ch.isLetter() } }
        val byLower = terms.associateBy { it.lowercase() }
        val tokens = word.findAll(text).toList()
        val out = StringBuilder()
        var cursor = 0
        var i = 0
        fun put(start: Int, end: Int, fixed: String) {
            out.append(text, cursor, start)
            out.append(fixed)
            cursor = end
        }
        while (i < tokens.size) {
            val token = tokens[i]
            val heard = token.value
            val capital = heard[0].isUpperCase()
            // "vox scribe" for "VoxScribe": one word the model split in two.
            val next = tokens.getOrNull(i + 1)
            if (next != null && text.substring(token.range.last + 1, next.range.first) == " ") {
                val joined = (heard + next.value).lowercase()
                val term = byLower[joined]
                if (term != null && joined.length >= MIN_JOINED && (joined in special || capital)) {
                    put(token.range.first, next.range.last + 1, term)
                    i += 2
                    continue
                }
            }
            val lower = heard.lowercase()
            val fixed = special[lower]
                // A plain name only fixes a word the model also took for a name.
                ?: if (capital && lower !in byLower) near(heard, names, common) else null
            if (fixed != null && fixed != heard) put(token.range.first, token.range.last + 1, fixed)
            i++
        }
        out.append(text, cursor, text.length)
        return out.toString()
    }

    /** The names on screen right now, or none when the setting is off or the floating button's service is not running. */
    fun capture(context: Context): List<String> {
        if (!TextToolsStore.snapshot(context).screenSpelling) return emptyList()
        val service = VoxScribeAccessibilityService.instance ?: return emptyList()
        return runCatching { terms(service.screenTexts(), common(context)) }.getOrDefault(emptyList())
    }

    // -- the common words, from the speech model's own word list -----------------

    @Volatile private var commonCache: Set<String>? = null

    /**
     * About 20,000 everyday lowercase words: the whole-word entries of the
     * bundled Whisper model's token list (base64, one per line). Empty when the
     * file is missing, which turns this feature off rather than guessing.
     */
    fun common(context: Context): Set<String> {
        commonCache?.let { return it }
        val words = HashSet<String>()
        runCatching {
            context.assets.open(WhisperEngine.TOKENS_ASSET).bufferedReader().useLines { lines ->
                for (line in lines) {
                    val encoded = line.substringBefore(' ')
                    val token = runCatching { String(Base64.decode(encoded, Base64.DEFAULT), Charsets.UTF_8) }.getOrNull() ?: continue
                    if (token.length < 2 || token[0] != ' ') continue
                    val w = token.substring(1)
                    if (w.all { it in 'a'..'z' }) words += w
                }
            }
        }
        return words.also { commonCache = it }
    }
}
