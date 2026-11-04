package com.voxscribe.android

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class LearnedWordsTest {

    private val common = setOf(
        "tell", "will", "call", "you", "at", "five", "the", "order", "on", "tuesday", "wednesday",
        "meet", "there", "their", "see", "great", "grate", "hi", "is", "ready", "any", "way", "anyway",
    )

    private fun fix(before: String, after: String, from: Int = 0) = LearnedWords.fix(before, after, from, common)

    @Test
    fun aMisheardNameFixedByHandIsLearned() {
        assertEquals(LearnedWords.Fix("Shivon", "Siobhan"), fix("Tell Shivon hi", "Tell Siobhan hi"))
        assertEquals(LearnedWords.Fix("Katerina", "Kateryna"), fix("Call Katerina at five", "Call Kateryna at five"))
    }

    @Test
    fun aCasingFixAndAJoinAreLearned() {
        assertEquals(LearnedWords.Fix("voxscribe", "VoxScribe"), fix("the voxscribe order", "the VoxScribe order"))
        assertEquals(LearnedWords.Fix("vox scribe", "VoxScribe"), fix("the vox scribe order", "the VoxScribe order"))
    }

    @Test
    fun changingWhatYouMeantIsNotLearned() {
        assertNull(fix("Meet on Tuesday", "Meet on Wednesday"))
        assertNull(fix("see you there", "see you their"))
        assertNull(fix("Tell Sarah hi", "Tell Emily hi"))
    }

    @Test
    fun onlyAClearOneWordFixCounts() {
        assertNull(fix("Tell Shivon hi", "Tell Shivon hi and more"))
        assertNull(fix("Tell Shivon hi", "Tell Siobhan hello there"))
        assertNull(fix("Tell Shivon hi", "Tell S hi"))
        assertNull(fix("Tell Shivon hi", ""))
    }

    @Test
    fun textThatWasThereBeforeTheDictationIsNotLearnedFrom() {
        val before = "Dear Shivon, the order is ready"
        assertNull(fix(before, "Dear Siobhan, the order is ready", from = 12))
        assertEquals(LearnedWords.Fix("Shivon", "Siobhan"), fix(before, "Dear Siobhan, the order is ready", from = 0))
    }

    @Test
    fun aFixOfAHalfTypedFixBecomesOneFix() {
        val first = LearnedWords.add(emptyList(), LearnedWords.Fix("Shivon", "Sio"))
        assertEquals(listOf(LearnedWords.Fix("Shivon", "Siobhan")), LearnedWords.add(first, LearnedWords.Fix("Sio", "Siobhan")))
    }

    @Test
    fun fixingALearnedWordBackForgetsIt() {
        val learned = listOf(LearnedWords.Fix("Shivon", "Siobhan"))
        assertEquals(emptyList<LearnedWords.Fix>(), LearnedWords.add(learned, LearnedWords.Fix("Siobhan", "Shivon")))
    }

    @Test
    fun theSameHeardWordKeepsOnlyTheNewestFix() {
        val learned = listOf(LearnedWords.Fix("Ahmed", "Ahmad"))
        assertEquals(listOf(LearnedWords.Fix("ahmed", "Ahmet")), LearnedWords.add(learned, LearnedWords.Fix("ahmed", "Ahmet")))
    }

    @Test
    fun learnedFixesApplyLikeReplacements() {
        val pairs = listOf(LearnedWords.Fix("Shivon", "Siobhan")).map { it.heard to it.fixed }
        assertEquals("Tell Siobhan hi", Replacements.apply("Tell shivon hi", pairs))
    }
}
