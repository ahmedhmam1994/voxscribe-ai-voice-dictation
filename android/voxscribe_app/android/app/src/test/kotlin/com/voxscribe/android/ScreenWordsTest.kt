package com.voxscribe.android

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ScreenWordsTest {

    private val common = setOf(
        "join", "send", "today", "john", "message", "the", "is", "at", "meet", "call", "and", "hi",
        "ask", "about", "app", "mark", "archive", "dictate", "tell", "on", "me", "to", "with", "new",
        "chat", "run", "sale", "total",
    )

    private fun fix(text: String, vararg screen: String): String =
        ScreenWords.correct(text, ScreenWords.terms(screen.toList(), common), common)

    @Test
    fun namesAndSpecialWordsAreTakenFromTheScreen() {
        val terms = ScreenWords.terms(listOf("Chat with Kateryna Nguyen", "Join", "Send on WhatsApp", "SALE", "B12"), common)
        assertEquals(setOf("Kateryna", "Nguyen", "WhatsApp", "B12"), terms.toSet())
    }

    @Test
    fun everydayWordsAndTheirFormsAreNeverNames() {
        assertTrue(ScreenWords.isCommon("archived", common))
        assertTrue(ScreenWords.isCommon("dictating", common))
        assertTrue(ScreenWords.isCommon("running", common))
        assertFalse(ScreenWords.isCommon("nguyen", common))
        assertTrue(ScreenWords.terms(listOf("Archived", "Dictating now"), common).isEmpty())
    }

    @Test
    fun aWordAlsoWrittenInLowerCaseIsNotAName() {
        assertTrue(ScreenWords.terms(listOf("Subtotal", "the subtotal is"), common).isEmpty())
    }

    @Test
    fun longCapitalLabelsAreNotAcronyms() {
        assertEquals(listOf("HIPAA"), ScreenWords.terms(listOf("SUBTOTAL", "HIPAA"), common))
    }

    @Test
    fun aSpecialWordGetsItsCasing() {
        assertEquals("Send it on WhatsApp", fix("Send it on whatsapp", "WhatsApp"))
        assertEquals("I take B12 today", fix("I take b12 today", "B12"))
    }

    @Test
    fun aWordTheModelSplitIsJoined() {
        assertEquals("Ask VoxScribe about it", fix("Ask vox scribe about it", "VoxScribe"))
    }

    @Test
    fun aMisspelledNameTakesTheScreenSpelling() {
        assertEquals("Tell Mohammed hi", fix("Tell Muhammad hi", "Mohammed"))
        assertEquals("Call Kateryna", fix("Call Katerina", "Kateryna"))
        assertEquals("Meet Sarah at 5", fix("Meet Sara at 5", "Sarah"))
    }

    @Test
    fun aPlainNameOnlyFixesAWordTheModelWroteAsAName() {
        assertEquals("tell muhammad hi", fix("tell muhammad hi", "Mohammed"))
    }

    @Test
    fun aButtonLabelNeverRewritesSpeech() {
        assertEquals("John will join", fix("John will join", "Join"))
        assertEquals("Call Kevin", fix("Call Kevin", "Gavin"))
    }

    @Test
    fun twoNamesEquallyCloseAreLeftAlone() {
        assertEquals("Call Jana", fix("Call Jana", "Jona", "Jena"))
    }

    @Test
    fun nothingChangesWithoutTheCommonWords() {
        assertEquals("on whatsapp", ScreenWords.correct("on whatsapp", listOf("WhatsApp"), emptySet()))
        assertTrue(ScreenWords.terms(listOf("WhatsApp"), emptySet()).isEmpty())
    }
}
