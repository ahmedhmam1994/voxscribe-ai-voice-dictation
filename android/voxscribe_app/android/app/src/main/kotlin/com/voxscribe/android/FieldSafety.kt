package com.voxscribe.android

/**
 * Which text fields VoxScribe may type into. A password field is never one of
 * them: the button stays hidden there, nothing is typed, and the undo command
 * never reads it. Dictating a secret would put it in the history and, on a
 * failed insert, on the clipboard.
 */
object FieldSafety {
    private const val CLASS_MASK = 0xF
    private const val VARIATION_MASK = 0xFF0

    private const val CLASS_TEXT = 0x1
    private const val CLASS_NUMBER = 0x2

    // android.text.InputType variations, spelled out so this can be tested off the device.
    private const val TEXT_PASSWORD = 0x80
    private const val TEXT_VISIBLE_PASSWORD = 0x90
    private const val TEXT_WEB_PASSWORD = 0xE0
    private const val NUMBER_PASSWORD = 0x10

    /** True for a password field, including the "show password" and numeric PIN variants. */
    fun isSensitive(isPassword: Boolean, inputType: Int): Boolean {
        if (isPassword) return true
        val variation = inputType and VARIATION_MASK
        return when (inputType and CLASS_MASK) {
            CLASS_TEXT -> variation == TEXT_PASSWORD ||
                variation == TEXT_VISIBLE_PASSWORD ||
                variation == TEXT_WEB_PASSWORD
            CLASS_NUMBER -> variation == NUMBER_PASSWORD
            else -> false
        }
    }

    /** Editable and not sensitive. */
    fun allowsDictation(isEditable: Boolean, isPassword: Boolean, inputType: Int): Boolean =
        isEditable && !isSensitive(isPassword, inputType)
}
