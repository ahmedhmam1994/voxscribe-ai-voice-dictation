package com.voxscribe.android

import org.junit.Assert.assertEquals
import org.junit.Test

class DictationTextTest {

    @Test
    fun firstDictationIntoAFieldIsJustTheNewText() {
        assertEquals("hello", DictationText.compose(current = "", lastWritten = null, dictated = "hello"))
    }

    @Test
    fun aPlaceholderIsReplacedNotKept() {
        assertEquals(
            "hello",
            DictationText.compose(current = "Message", lastWritten = null, dictated = "hello"),
        )
    }

    @Test
    fun theSameBoxStillHoldingOurTextKeepsAppending() {
        assertEquals(
            "hello there",
            DictationText.compose(current = "hello", lastWritten = "hello", dictated = " there"),
        )
    }

    @Test
    fun textTypedAfterOurDictationIsKept() {
        assertEquals(
            "hello world there",
            DictationText.compose(current = "hello world", lastWritten = "hello", dictated = " there"),
        )
    }

    @Test
    fun aDifferentChatReusingTheBoxDoesNotInheritTheOldText() {
        assertEquals(
            "second chat",
            DictationText.compose(current = "Message", lastWritten = "first chat", dictated = "second chat"),
        )
    }

    @Test
    fun aBoxClearedAfterSendingStartsFresh() {
        assertEquals(
            "next message",
            DictationText.compose(current = "", lastWritten = "sent message", dictated = "next message"),
        )
    }

    private val draft = "Hi Sam,\nHere is the first paragraph of my email.\n\nThanks"

    @Test
    fun anEmailDraftIsKeptAndDictationGoesAtTheEnd() {
        val r = DictationText.insertion(draft, null, "and more. ")
        assertEquals("$draft and more. ", r.text)
        assertEquals(r.text.length, r.cursor)
    }

    @Test
    fun dictationGoesAtTheCursorInTheMiddleOfADraft() {
        val at = draft.indexOf("\n\nThanks")
        val r = DictationText.insertion(draft, null, "really nice ", at, at)
        assertEquals(draft.substring(0, at) + " really nice" + draft.substring(at), r.text)
        assertEquals(at + " really nice".length, r.cursor)
    }

    @Test
    fun aCursorReportedAtZeroIsNotTrusted() {
        val r = DictationText.insertion(draft, null, "more. ", 0, 0)
        assertEquals(true, r.text.endsWith("more. "))
    }

    @Test
    fun aShortPlaceholderWithACursorIsStillReplaced() {
        assertEquals("hello", DictationText.insertion("Type a message", null, "hello", 3, 3).text)
    }

    @Test
    fun anEmptyRememberedWriteCountsAsFresh() {
        assertEquals(
            "hello",
            DictationText.compose(current = "Message", lastWritten = "", dictated = "hello"),
        )
    }
}
