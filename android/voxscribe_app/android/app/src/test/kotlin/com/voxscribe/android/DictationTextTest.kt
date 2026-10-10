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

    @Test
    fun anEmptyRememberedWriteCountsAsFresh() {
        assertEquals(
            "hello",
            DictationText.compose(current = "Message", lastWritten = "", dictated = "hello"),
        )
    }
}
