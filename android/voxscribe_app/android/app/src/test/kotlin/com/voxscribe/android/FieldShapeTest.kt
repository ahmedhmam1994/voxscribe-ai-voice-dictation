package com.voxscribe.android

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class FieldShapeTest {
    private val text = 0x1
    private val email = 0x21
    private val webEmail = 0xD1
    private val url = 0x11
    private val number = 0x2
    private val decimal = 0x2002
    private val signedDecimal = 0x3002
    private val phone = 0x3

    @Test
    fun ordinaryTextIsLeftAlone() {
        assertEquals("Sam at gmail dot com.", FieldShape.shape("Sam at gmail dot com.", text))
        assertEquals("Hi there.", FieldShape.shape("Hi there.", 0))
        assertFalse(FieldShape.noTrailingSpace(text))
    }

    @Test
    fun anEmailBoxGetsAnAddress() {
        assertEquals("sam@gmail.com", FieldShape.shape("Sam at gmail dot com.", email))
        assertEquals("sam@gmail.com", FieldShape.shape("Sam@gmail.com.", webEmail))
        assertEquals("j_doe-2@work.io", FieldShape.shape("J underscore doe dash two at work dot io", email))
        assertTrue(FieldShape.noTrailingSpace(email))
    }

    @Test
    fun aWebAddressBoxGetsAnAddress() {
        assertEquals("voxscribe.app/android", FieldShape.shape("voxscribe dot app slash android.", url))
        assertEquals("https://example.com", FieldShape.shape("https colon slash slash example dot com", url))
    }

    @Test
    fun aNumberBoxGetsOnlyDigits() {
        assertEquals("42", FieldShape.shape("42.", number))
        assertEquals("1250", FieldShape.shape("1,250", number))
        assertEquals("907", FieldShape.shape("nine zero seven", number))
        assertEquals("3.5", FieldShape.shape("three point five", decimal))
        assertEquals("35", FieldShape.shape("3.5", number))
        assertEquals("-12.5", FieldShape.shape("minus 12.5", signedDecimal))
        assertEquals("", FieldShape.shape("hello", number))
    }

    @Test
    fun aPhoneBoxGetsTheNumberYouSaid() {
        assertEquals("+15550123", FieldShape.shape("Plus 1 555 0123.", phone))
        assertEquals("5550100", FieldShape.shape("five five five oh one oh oh", phone))
        assertEquals("*21#", FieldShape.shape("star 21 hash", phone))
    }
}
