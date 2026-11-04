package com.voxscribe.android

import android.content.Context

/**
 * Learns your words: when you fix a word VoxScribe typed ("Shivon" to
 * "Siobhan"), the fix is kept and made for you from then on, like a word
 * replacement you never had to write.
 *
 * Only a clear spelling fix is learned: one word swapped for a similar one
 * (same first sound, mostly the same letters), a casing fix ("voxscribe" to
 * "VoxScribe") or two words joined ("vox scribe" to "VoxScribe"). Changing
 * what you meant ("Tuesday" to "Wednesday") is never learned, because
 * everyday words are left out on both sides. Kept on the phone only, and each
 * learned fix can be removed in Settings.
 */
object LearnedWords {

    const val MAX = 200
    private const val PREFS_NAME = "voxscribe_learned"
    private const val KEY_PAIRS = "pairs"
    private const val MIN_RATIO = 0.4

    private val word = Regex("[\\p{L}\\p{M}\\p{Nd}]+(?:['’][\\p{L}]+)?")

    data class Fix(val heard: String, val fixed: String)

    /**
     * The spelling fix that turned [before] (the box as VoxScribe left it) into
     * [after] (the box now), or null. Only words from [dictatedFrom] on count:
     * VoxScribe learns from what it typed, not from what was there before.
     */
    fun fix(before: String, after: String, dictatedFrom: Int, common: Set<String>): Fix? {
        if (common.isEmpty()) return null
        val old = word.findAll(before).toList()
        val new = word.findAll(after).toList()
        var head = 0
        while (head < old.size && head < new.size && old[head].value == new[head].value) head++
        var tail = 0
        while (tail < old.size - head && tail < new.size - head &&
            old[old.size - 1 - tail].value == new[new.size - 1 - tail].value
        ) {
            tail++
        }
        val changed = old.subList(head, old.size - tail)
        val typed = new.subList(head, new.size - tail)
        if (changed.isEmpty() || changed.size > 2 || typed.size != 1) return null
        if (changed.first().range.first < dictatedFrom) return null
        val fixed = typed[0].value
        val heard = changed.joinToString(" ") { it.value }
        if (fixed.length < 2 || !fixed.all { it.isLetter() } || changed.any { w -> !w.value.all { it.isLetter() } }) return null
        val fixedLower = fixed.lowercase()
        if (ScreenWords.isCommon(fixedLower, common)) return null
        if (changed.size == 2) {
            // "vox scribe" to "VoxScribe": the same letters, joined.
            return if (heard.replace(" ", "").lowercase() == fixedLower) Fix(heard, fixed) else null
        }
        val heardLower = heard.lowercase()
        if (heard == fixed || ScreenWords.isCommon(heardLower, common)) return null
        if (heardLower == fixedLower) return Fix(heard, fixed)
        val sameStart = heardLower[0] == fixedLower[0] || TermPacks.soft(heardLower[0], fixedLower[0])
        if (!sameStart || SequenceMatcher.ratio(heardLower, fixedLower) < MIN_RATIO) return null
        return Fix(heard, fixed)
    }

    /**
     * [lines] with [fix] added last. A fix for the same words, or one that undoes
     * it, goes. A fix of a learned fix ("Shivon => Sio", then "Sio" finished to
     * "Siobhan") becomes one fix from the first words.
     */
    fun add(lines: List<Fix>, fix: Fix): List<Fix> {
        val learned = learnedAs(lines, fix)
        val kept = lines.filterNot {
            it.heard.equals(learned.heard, ignoreCase = true) || it.heard.equals(learned.fixed, ignoreCase = true)
        }
        // Fixing a learned word back to what was heard just forgets it.
        if (learned.heard == learned.fixed) return kept
        return (kept + learned).takeLast(MAX)
    }

    private fun learnedAs(lines: List<Fix>, fix: Fix): Fix {
        val chained = lines.firstOrNull { it.fixed.equals(fix.heard, ignoreCase = true) }
        return if (chained != null) Fix(chained.heard, fix.fixed) else fix
    }

    // -- saved on the phone -----------------------------------------------------

    private fun prefs(context: Context) = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun all(context: Context): List<Fix> =
        Replacements.parse(prefs(context).getString(KEY_PAIRS, "").orEmpty()).map { (heard, fixed) -> Fix(heard, fixed) }

    /** The learned fixes as "heard => fixed" lines, the word replacements format. */
    fun text(context: Context): String = prefs(context).getString(KEY_PAIRS, "").orEmpty()

    private fun save(context: Context, fixes: List<Fix>) {
        prefs(context).edit().putString(KEY_PAIRS, fixes.joinToString("\n") { "${it.heard} => ${it.fixed}" }).apply()
    }

    /** Keeps [fix] and returns it as learned (see [add]), or null when it only undid a learned fix. */
    fun remember(context: Context, fix: Fix): Fix? {
        val lines = all(context)
        save(context, add(lines, fix))
        return learnedAs(lines, fix).takeIf { it.heard != it.fixed }
    }

    fun forget(context: Context, heard: String) = save(context, all(context).filterNot { it.heard.equals(heard, ignoreCase = true) })
}
