package com.voxscribe.android

/**
 * Teach VoxScribe your voice: finds the words the speech model gets wrong for
 * one speaker (an accent, a habit) so they can be fixed from then on. A port of
 * the Windows app's core/voice_teach.py, with the same sentences.
 *
 * The person reads a short script. Every sentence is written around a few
 * known terms. After each one is transcribed, what was heard is compared with
 * what was meant, looking only at those terms, and a replacement is proposed
 * for each one that came out differently. Nothing is applied until the person
 * ticks it, because a replacement changes that word everywhere they dictate.
 */
object VoiceTeach {

    data class Line(val sentence: String, val terms: List<String>)

    data class Slip(val heard: String, val expected: String)

    data class Proposal(val heard: String, val expected: String, val count: Int)

    /** Pack id to its sentences. Every term is a term of that pack (the tests check it). */
    val SENTENCES: Map<String, List<Line>> = linkedMapOf(
        "medical" to listOf(
            Line("She was prescribed amlodipine and atorvastatin for high blood pressure.", listOf("amlodipine", "atorvastatin")),
            Line("The doctor ordered a CBC, an HbA1c and a chest X-ray.", listOf("CBC", "HbA1c", "X-ray")),
            Line("He takes omeprazole in the morning and gabapentin at night.", listOf("omeprazole", "gabapentin")),
            Line("The ultrasound showed gallstones, so they scheduled a cholecystectomy.", listOf("cholecystectomy")),
            Line("Her TSH was high, so she started levothyroxine for hypothyroidism.", listOf("TSH", "levothyroxine", "hypothyroidism")),
            Line("The patient has atrial fibrillation and takes apixaban and bisoprolol.", listOf("atrial fibrillation", "apixaban", "bisoprolol")),
            Line("He was given amoxicillin for the infection and ibuprofen for the pain.", listOf("amoxicillin", "ibuprofen")),
            Line("The biopsy ruled out carcinoma, and the MRI showed no stroke.", listOf("carcinoma", "MRI")),
        ),
        "legal" to listOf(
            Line("The plaintiff filed a motion for summary judgment before the deposition.", listOf("plaintiff", "summary judgment", "deposition")),
            Line("Please sign the NDA before we discuss the indemnification clause.", listOf("NDA", "indemnification")),
            Line("The lawyer cited habeas corpus and the statute of limitations.", listOf("habeas corpus", "statute of limitations")),
            Line("The defendant received a subpoena and an affidavit from the court.", listOf("defendant", "subpoena", "affidavit")),
            Line("The fiduciary signed the power of attorney before the arbitration.", listOf("fiduciary", "power of attorney", "arbitration")),
            Line("The buyer asked about the lien and the escrow account.", listOf("lien", "escrow")),
            Line("The injunction was granted ex parte pending the hearing.", listOf("injunction", "ex parte")),
            Line("The testator named an executor and a beneficiary in the codicil.", listOf("testator", "executor", "beneficiary", "codicil")),
        ),
        "business" to listOf(
            Line("Our EBITDA grew this quarter, and the KPI report is due Friday.", listOf("EBITDA", "KPI")),
            Line("The client wants to renew the SLA before the end of Q3.", listOf("SLA", "Q3")),
            Line("We are tracking CAC, ARR and churn for the board meeting.", listOf("CAC", "ARR", "churn")),
            Line("The SaaS startup raised a seed round from an angel investor.", listOf("SaaS", "seed round", "angel investor")),
            Line("Her OKR is to improve the NPS and the conversion rate.", listOf("OKR", "NPS", "conversion rate")),
            Line("The CFO reviewed the balance sheet and the cash flow forecast.", listOf("CFO", "balance sheet", "cash flow")),
            Line("We signed the term sheet and started due diligence.", listOf("term sheet", "due diligence")),
            Line("The B2B pipeline depends on the go-to-market plan and the roadmap.", listOf("B2B", "pipeline", "go-to-market", "roadmap")),
        ),
    )

    const val DEFAULT_LENGTH = 10

    /** Words that are never worth a replacement on their own. */
    private val stopwords = (
        "a an and are as at be but by for from had has have he her his i in is it its of on or " +
            "she that the their them then there they this to was we were will with you your"
        ).split(" ").toSet()
    private val word = Regex("[\\w'’]+")

    /** The sentences to read: the enabled packs take turns; with none enabled, all built-in packs. */
    fun buildScript(enabled: List<String>, length: Int = DEFAULT_LENGTH): List<Line> {
        val packs = enabled.filter { it in SENTENCES }.ifEmpty { SENTENCES.keys.toList() }
        val script = mutableListOf<Line>()
        var index = 0
        while (script.size < length && packs.any { index < SENTENCES.getValue(it).size }) {
            for (pack in packs) {
                val lines = SENTENCES.getValue(pack)
                if (index < lines.size && script.size < length) script += lines[index]
            }
            index++
        }
        return script
    }

    /** Lowercase words; a hyphen separates words, so "X-ray" and "X ray" match. */
    private fun words(text: String): List<String> =
        word.findAll(text.lowercase().replace("-", " ")).map { it.value }.toList()

    private fun find(haystack: List<String>, needle: List<String>): Int {
        for (start in 0..haystack.size - needle.size) {
            if (haystack.subList(start, start + needle.size) == needle) return start
        }
        return -1
    }

    /**
     * The [targets] of [sentence] that [heard] has written differently. A target
     * is judged only when the words around it were heard right, so one garbled
     * stretch is not taken for several slips. A heard phrase that is itself a
     * known term is never proposed (that would turn a right word into another).
     */
    fun findSlips(sentence: String, targets: List<String>, heard: String, knownTerms: List<String> = emptyList()): List<Slip> {
        val expected = words(sentence)
        val got = words(heard)
        if (got.isEmpty()) return emptyList()
        val known = knownTerms.map { words(it).joinToString(" ") }.toSet()
        val heardOf = HashMap<Int, Int>()
        for (block in SequenceMatcher(expected, got).matchingBlocks) {
            for (offset in 0 until block.size) heardOf[block.aStart + offset] = block.bStart + offset
        }
        val slips = mutableListOf<Slip>()
        for (target in targets) {
            val targetWords = words(target)
            val start = find(expected, targetWords)
            if (start < 0) continue
            val end = start + targetWords.size
            if ((start until end).all { it in heardOf }) continue // heard right
            val left = start - 1
            if (left >= 0 && left !in heardOf) continue
            if (end < expected.size && end !in heardOf) continue
            val spanStart = if (left >= 0) heardOf.getValue(left) + 1 else 0
            val spanEnd = if (end < expected.size) heardOf.getValue(end) else got.size
            if (spanStart >= spanEnd) continue
            val span = got.subList(spanStart, spanEnd)
            if (span.size > targetWords.size + 2) continue
            val phrase = span.joinToString(" ")
            if (phrase == targetWords.joinToString(" ") || phrase in known) continue
            if (phrase.length < 3 || span.all { it in stopwords }) continue
            slips += Slip(phrase, target)
        }
        return slips
    }

    /** One proposal per distinct (heard, expected), most repeated first. */
    fun merge(slipLists: List<List<Slip>>): List<Proposal> {
        val seen = LinkedHashMap<Pair<String, String>, Proposal>()
        for (slip in slipLists.flatten()) {
            val key = slip.heard to slip.expected.lowercase()
            val found = seen[key]
            seen[key] = found?.copy(count = found.count + 1) ?: Proposal(slip.heard, slip.expected, 1)
        }
        return seen.values.sortedWith(compareBy({ -it.count }, { it.expected.lowercase() }))
    }
}
