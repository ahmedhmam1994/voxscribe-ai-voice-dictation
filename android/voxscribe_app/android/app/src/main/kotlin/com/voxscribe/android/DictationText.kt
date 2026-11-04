package com.voxscribe.android

/** Decides what a text field should hold after a dictation is inserted. */
object DictationText {

    /** Text and where the cursor goes once it has been inserted. */
    data class Result(val text: String, val cursor: Int)

    /** A field holding at least this much, or several lines, is real writing, not a placeholder. */
    private const val REAL_CONTENT_CHARS = 40

    /** [insertion] without a cursor: the dictation goes at the end. */
    fun compose(current: String, lastWritten: String?, dictated: String): String =
        insertion(current, lastWritten, dictated).text

    /**
     * [current] is what the field holds now, [lastWritten] is what VoxScribe
     * itself last wrote into it, [dictated] is the new text, and
     * [selStart]/[selEnd] are the cursor the field reports (-1 when unknown).
     *
     * The field's text is kept when it still starts with our last write (the
     * same message box is still in use) or when it looks like real writing, such
     * as an email draft. A short leftover like the "Message" placeholder, or a
     * box cleared after sending, starts fresh, so old dictation never comes back
     * into another conversation and a placeholder is never typed into.
     *
     * Kept text gets the dictation at the cursor. Many fields report the cursor
     * as 0,0 whatever the truth, so a cursor at the very start is not trusted
     * and the dictation goes at the end.
     */
    fun insertion(
        current: String,
        lastWritten: String?,
        dictated: String,
        selStart: Int = -1,
        selEnd: Int = -1,
    ): Result {
        if (dictated.isEmpty()) return Result(current, current.length)
        val continuing = !lastWritten.isNullOrEmpty() && current.startsWith(lastWritten)
        val realContent = current.length >= REAL_CONTENT_CHARS || current.contains('\n')
        if (!continuing && !realContent) return Result(dictated, dictated.length)

        val trusted = selStart > 0 && selEnd >= selStart && selEnd <= current.length
        val start = if (trusted) selStart else current.length
        val end = if (trusted) selEnd else current.length
        val before = current.substring(0, start)
        val after = current.substring(end)

        var piece = dictated
        // Keep words from running together. Our own chained dictations already
        // carry their trailing space, so this only matters for existing text.
        if (!continuing && before.isNotEmpty() && !before.last().isWhitespace() && !piece.first().isWhitespace()) {
            piece = " $piece"
        }
        if (after.isNotEmpty() && after.first().isWhitespace() && piece.last().isWhitespace()) {
            piece = piece.trimEnd()
        } else if (after.isNotEmpty() && !after.first().isWhitespace() && !piece.last().isWhitespace()) {
            piece += " "
        }
        return Result(before + piece + after, before.length + piece.length)
    }
}
