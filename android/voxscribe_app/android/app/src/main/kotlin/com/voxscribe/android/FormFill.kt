package com.voxscribe.android

import android.content.Context

/**
 * Speak once, fill the whole form: "Name Sam Lee, phone 0100 123 4567, email
 * sam at gmail dot com" puts each part into the box with that label. The boxes
 * and their labels come from the screen (see VoxScribeAccessibilityService's
 * formFields); this only matches the spoken labels to them, on the phone, with
 * no language model.
 *
 * To keep ordinary dictation ordinary, a sentence fills a form only when it
 * starts with a box's label and names at least two of the boxes on screen.
 */
object FormFill {

    /** A box on screen: its position in screen order, its label, and android.text.InputType. */
    data class Field(val index: Int, val label: String, val inputType: Int)

    /** What to type into the box at [index]. */
    data class Fill(val index: Int, val value: String)

    private const val MIN_FIELDS = 2

    /**
     * Ways people say a common label. A box labelled with any of these answers
     * to all of them, so "Mobile number" answers to "phone".
     */
    private val groups = listOf(
        listOf("first name", "given name", "forename"),
        listOf("last name", "surname", "family name"),
        listOf("middle name"),
        listOf("full name", "name", "your name"),
        listOf("phone number", "phone", "mobile number", "mobile", "telephone", "cell phone", "cell", "contact number"),
        listOf("email address", "email", "e mail", "e mail address", "mail"),
        listOf("street address", "address", "street", "address line 1"),
        listOf("address line 2", "apartment", "flat", "suite"),
        listOf("city", "town"),
        listOf("zip code", "zip", "postcode", "post code", "postal code"),
        listOf("state", "province", "region", "county"),
        listOf("country"),
        listOf("company", "company name", "organization", "organisation", "business"),
        listOf("job title", "position", "role"),
        listOf("date of birth", "birthday", "birth date", "dob"),
        listOf("age"),
        listOf("website", "web site", "url"),
        listOf("subject", "title"),
        listOf("message", "notes", "note", "comments", "comment", "description"),
    )

    /** Spoken before the first label without making the sentence ordinary speech. */
    private val leadIns = setOf("fill", "form", "my")

    private val wordPattern = Regex("[\\p{L}\\p{N}]+")
    private val labelNoise = Regex("\\(.*?\\)|[*:]|\\boptional\\b|\\brequired\\b|\\benter\\b|\\btype\\b|\\byour\\b")

    /** "Phone number *" or "Enter your e-mail:" as the bare words "phone number" / "e mail". */
    fun normalizeLabel(label: String): String =
        wordPattern.findAll(labelNoise.replace(label.lowercase(), " ")).joinToString(" ") { it.value }

    private val idPrefixes = setOf("et", "edit", "edittext", "input", "txt", "text", "field", "tv", "til")

    /** "com.app:id/et_phone_number" as "phone number", for a box with no visible label. */
    fun labelFromViewId(id: String?): String? {
        val name = id?.substringAfter('/')?.takeIf { it.isNotBlank() } ?: return null
        val words = name.replace(Regex("([a-z])([A-Z])"), "$1 $2").lowercase().split(Regex("[^a-z0-9]+"))
            .filter { it.isNotEmpty() && it !in idPrefixes }
        return words.joinToString(" ").ifEmpty { null }
    }

    /** Every way the box labelled [label] may be said. Empty when the label has no words. */
    fun aliases(label: String): Set<String> {
        val bare = normalizeLabel(label)
        if (bare.isEmpty()) return emptySet()
        val padded = " $bare "
        // The group whose longest phrase fits the label best: "first name" before "name".
        val group = groups
            .mapNotNull { group -> group.filter { " $it " in padded }.maxOfOrNull { it.length }?.let { group to it } }
            .maxByOrNull { it.second }
            ?.first
        // A label that is a group phrase itself takes the whole group; "Name of pet" stays itself.
        if (group != null && bare in group) return group.toSet() + bare
        // "Customer name" or "Home phone" ends in a common label, so it answers to it too.
        val words = bare.split(' ')
        if (words.size > 1 && words.first() !in notAKind) {
            val ending = groups.firstOrNull { group -> group.any { bare.endsWith(" $it") } }
            if (ending != null) return ending.toSet() + bare
        }
        return setOf(bare)
    }

    /** "User name" and "Pet name" are not the person's name. */
    private val notAKind = setOf("user", "nick", "screen", "display", "account", "pet", "file", "domain", "host", "project", "team", "group")

    private class Word(val text: String, val start: Int, val end: Int)

    private class Hit(val field: Field, val first: Int, val last: Int, val alias: String)

    private val wholeName = setOf("name", "full name", "your name")

    /**
     * What to type where, or null when [spoken] is not a form sentence for
     * [fields]. Fields without a label are ignored.
     */
    fun plan(spoken: String, fields: List<Field>): List<Fill>? {
        val labelled = fields.filter { aliases(it.label).isNotEmpty() }
        if (labelled.size < MIN_FIELDS) return null
        val words = wordPattern.findAll(spoken).map { Word(it.value.lowercase(), it.range.first, it.range.last + 1) }.toList()
        if (words.isEmpty()) return null

        val aliasSets = labelled.associateWith { aliases(it.label) }
        // A form with First name and Last name boxes but no Name box: "name Sam Lee" fills both.
        val firstNameBox = labelled.firstOrNull { "first name" in aliasSets.getValue(it) }
            ?.takeIf { labelled.none { field -> aliasSets.getValue(field).any { it in wholeName } } }
        val lastNameBox = labelled.firstOrNull { "last name" in aliasSets.getValue(it) }
        val aliasWords = labelled.associateWith { field ->
            val extra = if (field == firstNameBox && lastNameBox != null) wholeName else emptySet()
            (aliasSets.getValue(field) + extra).map { it.split(" ") }
        }
        val used = HashSet<Field>()
        val hits = mutableListOf<Hit>()
        var i = 0
        while (i < words.size) {
            // The longest label said here, given to the first box with it that is still empty.
            var best: Hit? = null
            for (field in labelled) {
                if (field in used) continue
                for (alias in aliasWords.getValue(field)) {
                    val last = i + alias.size - 1
                    if (last >= words.size) continue
                    if (alias.indices.all { words[i + it].text == alias[it] } &&
                        (best == null || last > best.last)
                    ) {
                        best = Hit(field, i, last, alias.joinToString(" "))
                    }
                }
            }
            if (best != null) {
                hits += best
                used += best.field
                i = best.last + 1
            } else {
                i++
            }
        }
        if (hits.size < MIN_FIELDS) return null
        val opening = hits.first().first
        if (opening > 1 || (opening == 1 && words[0].text !in leadIns)) return null

        val fills = hits.flatMapIndexed { n, hit ->
            val from = words[hit.last].end
            val to = hits.getOrNull(n + 1)?.let { words[it.first].start } ?: spoken.length
            val value = cleanValue(spoken.substring(from, to), hit.field.inputType)
            if (hit.field == firstNameBox && hit.alias in wholeName && lastNameBox != null && lastNameBox !in used) {
                splitName(value, hit.field.index, lastNameBox.index)
            } else {
                listOf(Fill(hit.field.index, value))
            }
        }.filter { it.value.isNotEmpty() }
        return if (fills.size >= MIN_FIELDS) fills else null
    }

    /**
     * True when [spoken] opens with a common label and names at least two, so it
     * is worth looking for boxes the screen has not shown yet.
     */
    fun startsLikeAForm(spoken: String): Boolean {
        val fields = groups.mapIndexed { i, group -> Field(i, group.first(), 0) }
        return plan(spoken, fields) != null
    }

    /** "Sam Lee" as Sam in the first name box and Lee in the last name box. */
    private fun splitName(value: String, firstIndex: Int, lastIndex: Int): List<Fill> {
        val parts = value.split(' ').filter { it.isNotEmpty() }
        if (parts.size < 2) return listOf(Fill(firstIndex, value))
        return listOf(
            Fill(firstIndex, parts.dropLast(1).joinToString(" ")),
            Fill(lastIndex, parts.last()),
        )
    }

    private val connector = Regex("^(?:is|are|=)\\s+", RegexOption.IGNORE_CASE)
    private val trailingAnd = Regex("\\s+and$", RegexOption.IGNORE_CASE)

    /** " is Sam Lee, " as "Sam Lee"; email, phone and number boxes get FieldShape's form. */
    fun cleanValue(raw: String, inputType: Int): String {
        var value = raw.trim().trim(',', ';', ':', '.', '-').trim()
        value = connector.replace(value, "")
        value = trailingAnd.replace(value, "").trim().trimEnd(',', ';', '.').trim()
        return FieldShape.shape(value, inputType).trim()
    }
}

/** Free form fills before Pro, kept on the phone like the free folder imports. */
object FormFillTries {
    const val FREE = 5
    private const val PREFS = "voxscribe_form_fill"
    private const val KEY_USED = "fills_used"

    /** Free fills left, or -1 with Pro (no limit). */
    fun left(context: Context): Int {
        if (LicenseStore.isPro(context)) return -1
        val used = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getInt(KEY_USED, 0)
        return (FREE - used).coerceAtLeast(0)
    }

    fun use(context: Context) {
        if (LicenseStore.isPro(context)) return
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        prefs.edit().putInt(KEY_USED, prefs.getInt(KEY_USED, 0) + 1).apply()
    }
}
