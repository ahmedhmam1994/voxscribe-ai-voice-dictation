package com.voxscribe.android

/**
 * Types dictation the way the focused box expects. An email box gets
 * "sam@gmail.com" for "Sam at gmail dot com.", a web address box gets
 * "voxscribe.app/android", and a number or phone box gets only the digits.
 * Every other box gets the text unchanged. Free, and needs no setting: the
 * app that drew the box already said what it is for.
 */
object FieldShape {
    enum class Kind { TEXT, EMAIL, URL, NUMBER, PHONE }

    private const val CLASS_MASK = 0xF
    private const val VARIATION_MASK = 0xFF0

    // android.text.InputType values, spelled out so this can be tested off the device.
    private const val CLASS_TEXT = 0x1
    private const val CLASS_NUMBER = 0x2
    private const val CLASS_PHONE = 0x3
    private const val TEXT_URI = 0x10
    private const val TEXT_EMAIL = 0x20
    private const val TEXT_WEB_EMAIL = 0xD0
    private const val NUMBER_FLAG_SIGNED = 0x1000
    private const val NUMBER_FLAG_DECIMAL = 0x2000

    fun kindOf(inputType: Int): Kind = when (inputType and CLASS_MASK) {
        CLASS_NUMBER -> Kind.NUMBER
        CLASS_PHONE -> Kind.PHONE
        CLASS_TEXT -> when (inputType and VARIATION_MASK) {
            TEXT_EMAIL, TEXT_WEB_EMAIL -> Kind.EMAIL
            TEXT_URI -> Kind.URL
            else -> Kind.TEXT
        }
        else -> Kind.TEXT
    }

    /** True when a space after the dictation would be wrong in this box. */
    fun noTrailingSpace(inputType: Int): Boolean = kindOf(inputType) != Kind.TEXT

    fun shape(text: String, inputType: Int): String = when (kindOf(inputType)) {
        Kind.TEXT -> text
        Kind.EMAIL -> address(text, emailWords)
        Kind.URL -> address(text, urlWords)
        Kind.NUMBER -> number(
            text,
            signed = inputType and NUMBER_FLAG_SIGNED != 0,
            decimal = inputType and NUMBER_FLAG_DECIMAL != 0,
        )
        Kind.PHONE -> phone(text)
    }

    private val emailWords = mapOf(
        "at" to "@", "dot" to ".", "underscore" to "_", "dash" to "-", "hyphen" to "-",
    )
    private val urlWords = emailWords + mapOf("slash" to "/", "colon" to ":")

    private val digitWords = mapOf(
        "zero" to "0", "one" to "1", "two" to "2", "three" to "3", "four" to "4",
        "five" to "5", "six" to "6", "seven" to "7", "eight" to "8", "nine" to "9",
    )

    private fun words(text: String): List<String> =
        text.trim().split(Regex("\\s+")).filter { it.isNotEmpty() }

    private fun address(text: String, spoken: Map<String, String>): String {
        val joined = words(text).joinToString("") { word ->
            val bare = word.trim(',', ';', '!', '?').lowercase()
            spoken[bare] ?: digitWords[bare] ?: bare
        }
        // A spoken sentence ends with a full stop; an address does not.
        return joined.trimEnd('.', ',', '!', '?')
    }

    private fun number(text: String, signed: Boolean, decimal: Boolean): String {
        val spoken = words(text).joinToString("") { word ->
            val bare = word.trim(',', '!', '?').lowercase()
            when {
                bare in digitWords -> digitWords.getValue(bare)
                bare == "point" && decimal -> "."
                bare == "minus" && signed -> "-"
                else -> bare
            }
        }
        val out = StringBuilder()
        for (c in spoken) {
            when {
                c.isDigit() -> out.append(c)
                c == '.' && decimal && '.' !in out -> out.append(c)
                c == '-' && signed && out.isEmpty() -> out.append(c)
            }
        }
        return out.toString().trimEnd('.')
    }

    private fun phone(text: String): String {
        val spoken = words(text).joinToString("") { word ->
            val bare = word.trim(',', '.', '!', '?').lowercase()
            when (bare) {
                in digitWords -> digitWords.getValue(bare)
                "oh" -> "0"
                "plus" -> "+"
                "star" -> "*"
                "hash", "pound" -> "#"
                else -> bare
            }
        }
        return spoken.filter { it.isDigit() || it == '+' || it == '*' || it == '#' }
    }
}
