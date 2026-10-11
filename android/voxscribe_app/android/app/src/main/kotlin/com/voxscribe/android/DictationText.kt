package com.voxscribe.android

/** Decides what a text field should hold after a dictation is inserted. */
object DictationText {

    /**
     * [current] is what the field holds now, [lastWritten] is what VoxScribe
     * itself last wrote into it, and [dictated] is the new text.
     *
     * The new text is appended only while the field still starts with our last
     * write, meaning the same message box is still in use. Anything else (the
     * box was cleared after sending, or a different chat reused it, or it shows
     * a placeholder such as "Message") starts fresh, so old dictation never
     * comes back into another conversation.
     */
    fun compose(current: String, lastWritten: String?, dictated: String): String {
        val continuing = !lastWritten.isNullOrEmpty() && current.startsWith(lastWritten)
        return if (continuing) current + dictated else dictated
    }
}
