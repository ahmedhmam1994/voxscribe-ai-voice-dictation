package com.voxscribe.android

/**
 * Code dictation, a Pro feature: speak identifiers and symbols, get code typed.
 * "camel case user name" becomes userName, "open paren x close paren" becomes
 * (x). A port of the Windows app's rules. Text in, text out, no model.
 *
 * It runs on the raw transcript in place of the prose cleanup and punctuation
 * commands, which would capitalize and add full stops, wrong for code.
 */
object CodeDictation {

    private val caseStyles: Map<String, (List<String>) -> String> = linkedMapOf(
        "camel case" to { w -> w[0] + w.drop(1).joinToString("") { it.replaceFirstChar(Char::uppercaseChar) } },
        "pascal case" to { w -> w.joinToString("") { it.replaceFirstChar(Char::uppercaseChar) } },
        "snake case" to { w -> w.joinToString("_") },
        "upper snake case" to { w -> w.joinToString("_").uppercase() },
        "constant case" to { w -> w.joinToString("_").uppercase() },
        "kebab case" to { w -> w.joinToString("-") },
        "dot case" to { w -> w.joinToString(".") },
    )

    /** A spoken symbol: its text, a space before (null means after a word, none), a space after. */
    private data class Symbol(val text: String, val spaceBefore: Boolean?, val spaceAfter: Boolean)

    private val symbols = linkedMapOf(
        "open paren" to Symbol("(", null, false),
        "open parenthesis" to Symbol("(", null, false),
        "close paren" to Symbol(")", false, true),
        "close parenthesis" to Symbol(")", false, true),
        "open bracket" to Symbol("[", null, false),
        "close bracket" to Symbol("]", false, true),
        "open brace" to Symbol("{", true, false),
        "close brace" to Symbol("}", false, true),
        "open curly" to Symbol("{", true, false),
        "close curly" to Symbol("}", false, true),
        "double equals" to Symbol("==", true, true),
        "not equals" to Symbol("!=", true, true),
        "equals" to Symbol("=", true, true),
        "plus" to Symbol("+", true, true),
        "minus" to Symbol("-", true, true),
        "times" to Symbol("*", true, true),
        "divided by" to Symbol("/", true, true),
        "less than" to Symbol("<", true, true),
        "greater than" to Symbol(">", true, true),
        "arrow" to Symbol("->", true, true),
        "fat arrow" to Symbol("=>", true, true),
        "colon" to Symbol(":", false, true),
        "semicolon" to Symbol(";", false, true),
        "comma" to Symbol(",", false, true),
        "dot" to Symbol(".", false, false),
        "underscore" to Symbol("_", false, false),
        "dash" to Symbol("-", false, false),
        "slash" to Symbol("/", false, false),
        "backslash" to Symbol("\\", false, false),
        "hash" to Symbol("#", true, false),
        "at sign" to Symbol("@", true, false),
        "ampersand" to Symbol("&", true, true),
        "pipe" to Symbol("|", true, true),
        "quote" to Symbol("\"", true, true),
        "single quote" to Symbol("'", true, true),
        "backtick" to Symbol("`", true, true),
    )

    private val lineBreaks = mapOf("new line" to "\n", "newline" to "\n", "tab" to "\t")

    private val phrases: List<String> =
        (caseStyles.keys + symbols.keys + lineBreaks.keys).sortedByDescending { it.split(" ").size }
    private val wordRe = Regex("[A-Za-z0-9']+")

    private fun tokens(text: String): List<String> =
        wordRe.findAll(text.lowercase().replace("-", " ")).map { it.value }.toList()

    private fun matchPhrase(words: List<String>, start: Int): String? {
        for (phrase in phrases) {
            val parts = phrase.split(" ")
            if (start + parts.size <= words.size && words.subList(start, start + parts.size) == parts) return phrase
        }
        return null
    }

    /** Turns a spoken transcript into code text. Empty input gives empty output. */
    fun toCode(text: String): String {
        val words = tokens(text)
        val out = StringBuilder()
        var glueNext = true // no space needed before the next piece
        var afterWord = false // the last thing emitted was an identifier or plain word

        fun emit(piece: String, spaceBefore: Boolean? = true, spaceAfter: Boolean = true, isWord: Boolean = false) {
            val needsSpace = if (spaceBefore == null) !afterWord else spaceBefore
            if (out.isNotEmpty() && needsSpace && !glueNext) out.append(' ')
            out.append(piece)
            glueNext = !spaceAfter
            afterWord = isWord
        }

        var i = 0
        while (i < words.size) {
            val phrase = matchPhrase(words, i)
            if (phrase == null) {
                emit(words[i], isWord = true)
                i += 1
                continue
            }
            i += phrase.split(" ").size
            when {
                phrase in caseStyles -> {
                    val run = mutableListOf<String>()
                    while (i < words.size && matchPhrase(words, i) == null) {
                        run.add(words[i])
                        i += 1
                    }
                    if (run.isNotEmpty()) emit(caseStyles.getValue(phrase)(run), isWord = true)
                }
                phrase in lineBreaks -> {
                    out.append(lineBreaks.getValue(phrase))
                    glueNext = true
                    afterWord = false
                }
                else -> {
                    val symbol = symbols.getValue(phrase)
                    emit(symbol.text, symbol.spaceBefore, symbol.spaceAfter)
                }
            }
        }
        return out.toString().trim(' ')
    }
}
