package com.voxscribe.android

import org.junit.Assert.assertEquals
import org.junit.Test
import java.time.LocalDateTime

class SnippetExpanderTest {
    private val snippets = listOf(
        Snippet("my email", "me@example.com"),
        Snippet("sign off", "Best regards, {date} at {time}"),
    )
    private val now = LocalDateTime.of(2026, 10, 10, 9, 5)

    @Test
    fun aTriggerBecomesItsExpansion() {
        assertEquals("me@example.com", SnippetExpander.expand("my email", snippets, now))
    }

    @Test
    fun caseAndEndPunctuationAreIgnored() {
        assertEquals("me@example.com", SnippetExpander.expand("  My Email. ", snippets, now))
    }

    @Test
    fun theDateAndTimeAreFilledIn() {
        assertEquals(
            "Best regards, 2026-10-10 at 09:05",
            SnippetExpander.expand("sign off", snippets, now),
        )
    }

    @Test
    fun aTriggerInsideALongerSentenceIsLeftAlone() {
        val sentence = "please send it to my email tomorrow"
        assertEquals(sentence, SnippetExpander.expand(sentence, snippets, now))
    }

    @Test
    fun withNoSnippetsTextIsUnchanged() {
        assertEquals("hello", SnippetExpander.expand("hello", emptyList(), now))
    }
}
