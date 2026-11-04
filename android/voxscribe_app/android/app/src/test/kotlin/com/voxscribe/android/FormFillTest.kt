package com.voxscribe.android

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

private const val TEXT = 0x1
private const val EMAIL = 0x21
private const val PHONE = 0x3

class FormFillTest {
    private val contact = listOf(
        FormFill.Field(0, "Name", TEXT),
        FormFill.Field(1, "Phone", PHONE),
        FormFill.Field(2, "Email", EMAIL),
        FormFill.Field(3, "City", TEXT),
    )

    private fun fills(spoken: String, fields: List<FormFill.Field> = contact): Map<Int, String>? =
        FormFill.plan(spoken, fields)?.associate { it.index to it.value }

    @Test fun fillsEveryNamedBox() {
        assertEquals(
            mapOf(0 to "Sam Lee", 1 to "01001234567", 2 to "sam@gmail.com", 3 to "Cairo"),
            fills("Name Sam Lee, phone 0100 123 4567, email Sam at gmail dot com, city Cairo."),
        )
    }

    @Test fun ordinaryDictationIsLeftAlone() {
        // Starts with ordinary words, so it is a message, not a form.
        assertNull(fills("Call me on my phone when you reach the city."))
        // Only one box named.
        assertNull(fills("Name Sam Lee."))
        assertNull(fills(""))
    }

    @Test fun aShortLeadInIsAllowed() {
        assertEquals(mapOf(0 to "Sam", 3 to "Cairo"), fills("My name is Sam and city is Cairo"))
        assertNull(fills("Please name Sam, city Cairo"))
    }

    @Test fun labelsMatchTheirCommonWords() {
        val fields = listOf(
            FormFill.Field(0, "First name *", TEXT),
            FormFill.Field(1, "Last name", TEXT),
            FormFill.Field(2, "Mobile number (optional)", PHONE),
            FormFill.Field(3, "Enter your e-mail:", EMAIL),
        )
        assertEquals(
            mapOf(0 to "Sam", 1 to "Lee", 2 to "0100", 3 to "sam@x.com"),
            fills("first name Sam surname Lee phone oh one oh oh email sam at x dot com", fields),
        )
    }

    @Test fun longestLabelWins() {
        val fields = listOf(FormFill.Field(0, "Name", TEXT), FormFill.Field(1, "First name", TEXT))
        assertEquals(mapOf(1 to "Sam", 0 to "Sam Lee"), fills("first name Sam, name Sam Lee", fields))
    }

    @Test fun twoBoxesWithTheSameLabelFillInScreenOrder() {
        val fields = listOf(FormFill.Field(0, "Phone", PHONE), FormFill.Field(1, "Phone", PHONE))
        assertEquals(mapOf(0 to "111", 1 to "222"), fills("phone 111 phone 222", fields))
    }

    @Test fun unlabelledBoxesAreIgnored() {
        val fields = listOf(FormFill.Field(0, "", TEXT), FormFill.Field(1, "Name", TEXT))
        assertNull(fills("name Sam city Cairo", fields))
    }

    @Test fun aLabelThatIsNotACommonPhraseStaysItself() {
        assertEquals(setOf("name of pet"), FormFill.aliases("Name of pet"))
        assertEquals(true, "mobile" in FormFill.aliases("Phone number"))
        assertEquals(emptySet<String>(), FormFill.aliases("*"))
    }

    @Test fun aFullNameSplitsIntoFirstAndLastNameBoxes() {
        // Google Contacts: First name, Last name, Company, Phone (Mobile), no Name box.
        val fields = listOf(
            FormFill.Field(0, "First name", TEXT),
            FormFill.Field(1, "Last name", TEXT),
            FormFill.Field(2, "Company", TEXT),
            FormFill.Field(3, "Phone (Mobile)", PHONE),
        )
        assertEquals(
            mapOf(0 to "Sam", 1 to "Lee", 3 to "01001234567"),
            fills("Name Sam Lee, phone 0100 123 4567, email sam at gmail dot com", fields),
        )
        // Said separately, each name goes where it was said.
        assertEquals(mapOf(0 to "Sam Ann", 1 to "Lee"), fills("first name Sam Ann last name Lee", fields))
    }

    @Test fun aNameBoxKeepsTheWholeName() {
        val fields = listOf(FormFill.Field(0, "Name", TEXT), FormFill.Field(1, "Last name", TEXT))
        assertEquals(mapOf(0 to "Sam Lee", 1 to "Lee"), fills("name Sam Lee, last name Lee", fields))
    }

    @Test fun aWebFormAnswersToItsCommonWords() {
        // httpbin.org/forms/post, labels read from the page.
        val fields = listOf(
            FormFill.Field(0, "Customer name:", TEXT),
            FormFill.Field(1, "Telephone:", PHONE),
            FormFill.Field(2, "E-mail address:", EMAIL),
            FormFill.Field(3, "Delivery instructions:", TEXT),
        )
        assertEquals(
            mapOf(0 to "Sam Lee", 1 to "01001234567", 2 to "sam@gmail.com", 3 to "ring twice"),
            fills("Name Sam Lee, phone 0100 123 4567, email sam at gmail dot com, delivery instructions ring twice", fields),
        )
        assertEquals(setOf("user name"), FormFill.aliases("User name"))
    }

    @Test fun aFormSentenceIsKnownBeforeItsBoxesShow() {
        assertEquals(true, FormFill.startsLikeAForm("Name Sam Lee, company Acme, phone 0100"))
        assertEquals(false, FormFill.startsLikeAForm("Call me on my phone when you reach the city."))
        assertEquals(false, FormFill.startsLikeAForm("Name Sam Lee."))
    }

    @Test fun viewIdsBecomeLabels() {
        assertEquals("phone number", FormFill.labelFromViewId("com.app:id/et_phone_number"))
        assertEquals("email", FormFill.labelFromViewId("com.app:id/inputEmail"))
        assertNull(FormFill.labelFromViewId("com.app:id/et"))
        assertNull(FormFill.labelFromViewId(null))
    }

    @Test fun valuesLoseConnectorsAndPunctuation() {
        assertEquals("Sam Lee", FormFill.cleanValue(" is Sam Lee, and", TEXT))
        assertEquals("sam@gmail.com", FormFill.cleanValue(" sam at gmail dot com.", EMAIL))
    }
}
