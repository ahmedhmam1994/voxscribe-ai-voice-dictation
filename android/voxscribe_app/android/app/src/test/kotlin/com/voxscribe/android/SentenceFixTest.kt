package com.voxscribe.android

import org.junit.Assert.assertEquals
import org.junit.Test

class SentenceFixTest {

    @Test
    fun aMissingFullStopBeforeACapitalOpenerIsAdded() {
        assertEquals(
            "We start on Monday at 9:30 AM. The first phase covers the database.",
            SentenceFix.fix("We start on Monday at 9:30 AM The first phase covers the database"),
        )
    }

    @Test
    fun titlesAndNamesAreLeftAlone() {
        assertEquals("I read Lord of The Rings last week.", SentenceFix.fix("I read Lord of The Rings last week"))
        assertEquals("Hi Sam, Thanks for the draft.", SentenceFix.fix("Hi Sam, Thanks for the draft"))
    }

    @Test
    fun existingPunctuationIsKept() {
        assertEquals("Thanks. The plan works.", SentenceFix.fix("Thanks. The plan works."))
    }

    @Test
    fun shortFragmentsGetNoFullStop() {
        assertEquals("sounds good", SentenceFix.fix("sounds good"))
        assertEquals("sam@example.com is the address for you", SentenceFix.fix("sam@example.com is the address for you"))
    }

    @Test
    fun aBareLastSentenceIsClosed() {
        assertEquals("The budget is lower than last quarter.", SentenceFix.fix("The budget is lower than last quarter"))
    }

    @Test
    fun bigNumbersGetCommas() {
        assertEquals("The budget is \$25,000.", SmartFormat.format("The budget is twenty five thousand dollars."))
    }

    @Test
    fun spokenCodesMadeOfNumberWordsJoinUp() {
        assertEquals("The order number 4829 is ready", SmartFormat.format("The order number four eight twenty nine is ready"))
        assertEquals("extension 5501", SmartFormat.format("extension five five oh one"))
        assertEquals("order 25", SmartFormat.format("order twenty five"))
    }
}
