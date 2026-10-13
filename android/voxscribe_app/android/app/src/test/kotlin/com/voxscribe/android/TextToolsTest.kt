package com.voxscribe.android

import java.time.LocalDateTime
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** The text tools are ports of the Windows app's modules, so these mirror its tests. */
class VoiceCommandsTest {
    private fun apply(text: String) = VoiceCommands.apply(text)

    @Test fun emptyAndBlankPassThrough() {
        assertEquals("", apply(""))
        assertEquals("   ", apply("   "))
    }

    @Test fun noCommandsPassesThrough() = assertEquals("no commands here at all", apply("no commands here at all"))

    @Test fun periodAndComma() = assertEquals("hello, world.", apply("hello comma world period"))

    @Test fun capitalizesAfterAnEndOfSentenceCommand() =
        assertEquals("hello. The next word", apply("hello period the next word"))

    @Test fun questionMarkAndExclamation() {
        assertEquals("what time is it?", apply("what time is it question mark"))
        assertEquals("call me maybe!", apply("call me maybe exclamation point"))
        assertEquals("call me maybe!", apply("call me maybe exclamation mark"))
    }

    @Test fun fullStopIsAnAliasForPeriod() = assertEquals("that is all.", apply("that is all full stop"))

    @Test fun colonAndSemicolon() = assertEquals(
        "item one: apples, oranges; and pears",
        apply("item one colon apples comma oranges semicolon and pears"),
    )

    @Test fun newLineAndNewParagraph() {
        assertEquals("hello\nWorld", apply("hello new line world"))
        assertEquals("hello\n\nWorld", apply("hello new paragraph world"))
    }

    @Test fun quotes() = assertEquals(
        "she said \"hello\" and left",
        apply("she said open quote hello close quote and left"),
    )

    @Test fun parenthesesAndTheirLongForms() {
        assertEquals("call me (maybe) today", apply("call me open paren maybe close paren today"))
        assertEquals("call me (maybe) today", apply("call me open parenthesis maybe close parenthesis today"))
    }

    @Test fun isCaseInsensitive() = assertEquals("hello, world.", apply("hello COMMA world PERIOD"))

    @Test fun noLeftoverCapitalizationMarker() {
        val result = apply("hello period world period new line done")
        assertFalse(result.contains('\uE000'))
        assertFalse(result.contains('\u0000'))
    }

    @Test fun editingCommandsMatchTheWholeUtteranceOnly() {
        assertEquals(VoiceCommands.Edit.ALL, VoiceCommands.editingCommand("scratch that"))
        assertEquals(VoiceCommands.Edit.ALL, VoiceCommands.editingCommand("Scratch that."))
        assertEquals(VoiceCommands.Edit.ALL, VoiceCommands.editingCommand("UNDO THAT"))
        assertEquals(VoiceCommands.Edit.ALL, VoiceCommands.editingCommand("undo"))
        assertEquals(VoiceCommands.Edit.WORD, VoiceCommands.editingCommand("delete last word"))
        assertEquals(VoiceCommands.Edit.WORD, VoiceCommands.editingCommand("Delete that word."))
        assertEquals(VoiceCommands.Edit.SENTENCE, VoiceCommands.editingCommand("delete last sentence"))
        assertEquals(VoiceCommands.Edit.SENTENCE, VoiceCommands.editingCommand("scratch that sentence"))
        assertNull(VoiceCommands.editingCommand("scratch that itch"))
        assertNull(VoiceCommands.editingCommand("please undo that email"))
        assertNull(VoiceCommands.editingCommand("hello world"))
        assertNull(VoiceCommands.editingCommand(""))
    }

    @Test fun aMishearingOfAnEditingCommandStillCounts() {
        // What the phone's small model really produced for "scratch that".
        assertEquals(VoiceCommands.Edit.ALL, VoiceCommands.editingCommand("Scratch Z."))
        assertEquals(VoiceCommands.Edit.ALL, VoiceCommands.editingCommand("Scraach the"))
        assertEquals(VoiceCommands.Edit.ALL, VoiceCommands.editingCommand("scratch this."))
        // Every way the phone has actually written it so far.
        assertEquals(VoiceCommands.Edit.ALL, VoiceCommands.editingCommand("Scrape Z"))
        assertEquals(VoiceCommands.Edit.ALL, VoiceCommands.editingCommand("Scratch it."))
        assertEquals(VoiceCommands.Edit.ALL, VoiceCommands.editingCommand("Scrape the top."))
        assertEquals(VoiceCommands.Edit.ALL, VoiceCommands.editingCommand("Scratch the toe."))
        assertEquals(VoiceCommands.Edit.ALL, VoiceCommands.editingCommand("Scrab this."))
        assertNull(VoiceCommands.editingCommand("scratch the surface"))
        assertNull(VoiceCommands.editingCommand("scratch the itch"))
        assertEquals(VoiceCommands.Edit.ALL, VoiceCommands.editingCommand("Scrap that."))
        assertEquals(VoiceCommands.Edit.ALL, VoiceCommands.editingCommand("Cancel that"))
        assertEquals(VoiceCommands.Edit.WORD, VoiceCommands.editingCommand("delete last wood"))
        assertEquals(VoiceCommands.Edit.SENTENCE, VoiceCommands.editingCommand("delete last sentense"))
    }

    @Test fun ordinaryShortDictationIsNotMistakenForACommand() {
        assertNull(VoiceCommands.editingCommand("scratch that itch"))
        assertNull(VoiceCommands.editingCommand("scratch pad"))
        assertNull(VoiceCommands.editingCommand("delete the file"))
        assertNull(VoiceCommands.editingCommand("hello there"))
        assertNull(VoiceCommands.editingCommand("good morning"))
        assertNull(VoiceCommands.editingCommand("see you later"))
        assertNull(VoiceCommands.editingCommand("undue"))
        assertNull(VoiceCommands.editingCommand("what time"))
    }

    @Test fun deletionAllClearsEverything() {
        assertEquals(VoiceCommands.Deletion("", 11), VoiceCommands.computeDeletion("hello there", VoiceCommands.Edit.ALL))
        assertEquals(VoiceCommands.Deletion("", 0), VoiceCommands.computeDeletion("", VoiceCommands.Edit.ALL))
    }

    @Test fun deletionWordRemovesTheLastWordAndItsSpace() {
        assertEquals(
            VoiceCommands.Deletion("hello there", 7),
            VoiceCommands.computeDeletion("hello there friend", VoiceCommands.Edit.WORD),
        )
        assertEquals(VoiceCommands.Deletion("", 5), VoiceCommands.computeDeletion("hello", VoiceCommands.Edit.WORD))
        assertEquals(
            VoiceCommands.Deletion("hello", 7),
            VoiceCommands.computeDeletion("hello there ", VoiceCommands.Edit.WORD),
        )
    }

    @Test fun deletionSentenceRemovesTheLastSentenceOnly() {
        assertEquals(
            VoiceCommands.Deletion("First one.", 12),
            VoiceCommands.computeDeletion("First one. Second one.", VoiceCommands.Edit.SENTENCE),
        )
        assertEquals(
            VoiceCommands.Deletion("", 18),
            VoiceCommands.computeDeletion("Just one sentence.", VoiceCommands.Edit.SENTENCE),
        )
        assertEquals(
            VoiceCommands.Deletion("", 19),
            VoiceCommands.computeDeletion("No terminators here", VoiceCommands.Edit.SENTENCE),
        )
    }
}

class ReplacementsTest {
    @Test fun parseSkipsBadLinesAndAllowsAnEmptyReplacement() {
        val text = "vox scribe => VoxScribe\nno arrow here\n => nothing\nuh huh =>\n"
        assertEquals(listOf("vox scribe" to "VoxScribe", "uh huh" to ""), Replacements.parse(text))
    }

    @Test fun wholeWordCaseInsensitive() = assertEquals(
        "I use VoxScribe daily.",
        Replacements.apply("I use Vox Scribe daily.", listOf("vox scribe" to "VoxScribe")),
    )

    @Test fun doesNotReplaceInsideLongerWords() = assertEquals(
        "concatenate the dog",
        Replacements.apply("concatenate the cat", listOf("cat" to "dog")),
    )

    @Test fun emptyReplacementDeletesTheWordAndTidiesSpacing() = assertEquals(
        "It is done,.",
        Replacements.apply("It is basically done, basically.", listOf("basically" to "")),
    )

    @Test fun replacementTextIsLiteralNotRegex() = assertEquals(
        "the C:\\new\\1 here",
        Replacements.apply("the path here", listOf("path" to "C:\\new\\1")),
    )

    @Test fun noPairsLeavesPlainTextUnchanged() = assertEquals("hello world", Replacements.apply("hello world", emptyList()))

    @Test fun emptyText() = assertEquals("", Replacements.apply("", listOf("a" to "b")))
}

class SmartFormatTest {
    private fun f(text: String) = SmartFormat.format(text)

    @Test fun emails() {
        assertEquals("john.smith@gmail.com", f("john dot smith at gmail dot com"))
        assertEquals("email me at sam_dev@acme.io please", f("email me at sam underscore dev at acme dot io please"))
        assertEquals("send it to anna@work.org.", f("send it to Anna at work dot org."))
    }

    @Test fun anOrdinaryWordBeforeAtIsNotAnEmail() = assertEquals("look at example.com", f("look at example dot com"))

    @Test fun webAddresses() {
        assertEquals("example.com", f("example dot com"))
        assertEquals("example.com/pricing", f("example dot com slash pricing"))
        assertEquals("www.example.org", f("w w w dot example dot org"))
        assertEquals("https://my-site.dev/docs", f("https colon slash slash my dash site dot dev slash docs"))
    }

    @Test fun numbers() {
        assertEquals("25%", f("twenty five percent"))
        assertEquals("$105", f("one hundred and five dollars"))
        assertEquals("2026", f("two thousand twenty six"))
        assertEquals("3.5", f("three point five"))
        assertEquals("5%", f("five percent"))
        assertEquals("a total of 42 items", f("a total of forty two items"))
        assertEquals("11", f("eleven"))
    }

    @Test fun aLoneSmallNumberStaysAWord() = assertEquals("one of them and two more", f("one of them and two more"))

    @Test fun aPhraseThatDoesNotParseIsLeftAlone() = assertEquals("twenty twenty six", f("twenty twenty six"))

    @Test fun aRunOfSpokenDigitsBecomesAPhoneNumber() =
        assertEquals("call 5551234 now", f("call five five five one two three four now"))

    @Test fun plainAndEmptyTextAreUnchanged() {
        assertEquals("Hello there, how are you?", f("Hello there, how are you?"))
        assertEquals("", f(""))
    }

    @Test fun parseNumberWords() {
        assertEquals(123, SmartFormat.parseNumberWords("one hundred twenty three"))
        assertEquals(999, SmartFormat.parseNumberWords("nine hundred ninety nine"))
        assertEquals(1_000_000, SmartFormat.parseNumberWords("one million"))
    }
}

class CodeDictationTest {
    private fun code(text: String) = CodeDictation.toCode(text)

    @Test fun caseStyles() {
        assertEquals("userName", code("camel case user name"))
        assertEquals("UserName", code("pascal case user name"))
        assertEquals("user_name", code("snake case user name"))
        assertEquals("MAX_RETRY_COUNT", code("upper snake case max retry count"))
        assertEquals("API_KEY", code("constant case api key"))
        assertEquals("main-header", code("kebab case main header"))
        assertEquals("app.config", code("dot case app config"))
    }

    @Test fun aCaseCommandStopsAtTheNextSymbol() =
        assertEquals("getUser(id)", code("camel case get user open paren id close paren"))

    @Test fun assignmentGetsSpacesAroundEquals() =
        assertEquals("total_count = zero", code("snake case total count equals zero"))

    @Test fun twoIdentifiersInOneLine() =
        assertEquals("userName = firstName", code("camel case user name equals camel case first name"))

    @Test fun bracketsAttachToTheirContents() =
        assertEquals("[one, two]", code("open bracket one comma two close bracket"))

    @Test fun wordsWithNoCaseCommandAreKept() = assertEquals("return value", code("return value"))

    @Test fun aNewLineBreaksTheLine() = assertEquals("import os\nimport sys", code("import os new line import sys"))

    @Test fun longerPhraseWinsOverAShorterOne() = assertEquals("a == b", code("a double equals b"))

    @Test fun dotJoinsAMemberAccess() = assertEquals("self.user_id", code("self dot snake case user id"))

    @Test fun punctuationInTheTranscriptIsIgnored() = assertEquals("userName", code("Camel case, user name."))

    @Test fun emptyInputGivesEmptyOutput() = assertEquals("", code(""))
}

class TemplatesTest {
    private val bug = Template("bug report", "Title: {title}\nSteps: {steps}\nFiled {date}")
    private val now = LocalDateTime.of(2026, 10, 11, 9, 5)

    @Test fun slotsSkipDateAndTimeAndRepeats() =
        assertEquals(listOf("title", "steps"), Templates.slotNames("{title} {date} {time} {steps} {title}"))

    @Test fun bothTriggerWordsFindTheTemplate() {
        assertEquals(bug, Templates.find("Template bug report.", listOf(bug)))
        assertEquals(bug, Templates.find("fill bug report", listOf(bug)))
    }

    @Test fun aTriggerInsideASentenceIsNotATemplate() = assertNull(Templates.find("please fill bug report now", listOf(bug)))

    @Test fun anUnknownNameFindsNothing() = assertNull(Templates.find("template invoice", listOf(bug)))

    @Test fun sessionAsksSlotsInOrderAndRenders() {
        val session = Templates.Session(bug, now)
        assertEquals("title", session.prompt)
        session.feed("Login fails.")
        assertEquals("steps", session.prompt)
        session.feed("Open the app, then tap sign in. It crashes.")
        assertTrue(session.finished)
        assertEquals(
            "Title: Login fails\nSteps: Open the app, then tap sign in. It crashes.\nFiled 2026-10-11",
            session.result(),
        )
    }

    @Test fun skipLeavesTheSlotEmpty() {
        val session = Templates.Session(bug, now)
        assertEquals("skip", session.feed("skip"))
        session.feed("Some steps")
        assertTrue(session.result().startsWith("Title: \nSteps: Some steps"))
    }

    @Test fun cancelIsReported() = assertEquals("cancel", Templates.Session(bug, now).feed("Cancel."))

    @Test fun settingsTextRoundTripsWithLineBreaks() {
        val items = listOf(Template("bug report", "Title: {title}\nSteps: {steps}"), Template("hi", "Hello"))
        assertEquals(items, Templates.parseLines(Templates.formatLines(items)))
    }

    @Test fun parsingSkipsLinesWithoutANameOrBody() {
        val text = "no arrow here\n => only a body\nname only =>\nok => fine"
        assertEquals(listOf(Template("ok", "fine")), Templates.parseLines(text))
    }
}

class AppProfilesTest {
    @Test fun aLineSetsFlags() = assertEquals(
        mapOf("com.termux" to mapOf("code" to true, "cleanup" to false)),
        AppProfiles.parseLines("Com.Termux => code=on, cleanup=off"),
    )

    @Test fun badLinesOptionsAndValuesAreDropped() {
        val text = "no arrow\n => code=on\ncom.x => speed=fast, cleanup=maybe\ncom.y => smart=yes\ncom.z => language=ar"
        assertEquals(mapOf("com.y" to mapOf("smart" to true)), AppProfiles.parseLines(text))
    }

    @Test fun lookupIsCaseInsensitiveAndEmptyWhenMissing() {
        val profiles = AppProfiles.parseLines("com.termux => code=on")
        assertEquals(mapOf("code" to true), AppProfiles.optionsFor(profiles, "COM.TERMUX"))
        assertEquals(emptyMap<String, Boolean>(), AppProfiles.optionsFor(profiles, "com.other"))
        assertEquals(emptyMap<String, Boolean>(), AppProfiles.optionsFor(profiles, null))
    }
}

class TextPipelineTest {
    private val pro = TextOptions(
        pro = true, cleanup = true, voiceCommands = true, smartFormat = true, codeDictation = false,
        replacements = listOf("vox scribe" to "VoxScribe"),
        snippets = listOf(Snippet("my email", "me@example.com")),
        templates = listOf(Template("bug report", "Title: {title}\nSteps: {steps}")),
    )
    private val free = pro.copy(pro = false)

    private fun text(spoken: Spoken) = (spoken as Spoken.Text).text

    @Test fun cleanupThenVoiceCommandsThenSmartFormatThenReplacements() {
        val spoken = TextPipeline.process(
            "um tell anna at work dot org that vox scribe is out comma twenty five percent faster period",
            pro,
        )
        assertEquals("Tell anna@work.org that VoxScribe is out, 25% faster.", text(spoken))
    }

    @Test fun freeTierKeepsVoiceCommandsAndReplacementsButNotSmartFormat() {
        val spoken = TextPipeline.process("hello comma vox scribe at gmail dot com", free)
        assertEquals("Hello, VoxScribe at gmail dot com", text(spoken))
    }

    @Test fun aSnippetTriggerIsExpandedOnlyForPro() {
        assertEquals("me@example.com", text(TextPipeline.process("my email", pro)))
        assertEquals("My email", text(TextPipeline.process("my email", free)))
    }

    @Test fun codeDictationReplacesProseCleanup() {
        val options = pro.copy(codeDictation = true)
        assertEquals("userName", text(TextPipeline.process("Camel case, user name.", options)))
    }

    @Test fun editingCommandsOnlyWhenInteractiveAndEnabled() {
        assertEquals(Spoken.Edit(VoiceCommands.Edit.ALL), TextPipeline.process("scratch that", pro, interactive = true))
        assertEquals(
            Spoken.Edit(VoiceCommands.Edit.WORD),
            TextPipeline.process("delete last word.", pro, interactive = true),
        )
        assertTrue(TextPipeline.process("scratch that", pro, interactive = false) is Spoken.Text)
        assertTrue(TextPipeline.process("scratch that", pro.copy(voiceCommands = false), interactive = true) is Spoken.Text)
    }

    @Test fun aTemplateIsFilledOverSeveralUtterances() {
        val state = TextPipeline.TemplateState()
        val first = TextPipeline.process("template bug report", pro, interactive = true, state = state, nowMs = 0)
        assertEquals(Spoken.TemplatePrompt("bug report", "title"), first)
        val second = TextPipeline.process("Login fails.", pro, interactive = true, state = state, nowMs = 1_000)
        assertEquals(Spoken.TemplatePrompt("bug report", "steps"), second)
        val done = TextPipeline.process("Open the app.", pro, interactive = true, state = state, nowMs = 2_000)
        assertEquals(Spoken.Text("Title: Login fails\nSteps: Open the app"), done)
        assertNull(state.session)
    }

    @Test fun aTemplateCanBeCancelledAndTimesOut() {
        val state = TextPipeline.TemplateState()
        TextPipeline.process("template bug report", pro, interactive = true, state = state, nowMs = 0)
        assertEquals(
            Spoken.TemplateCancelled,
            TextPipeline.process("cancel", pro, interactive = true, state = state, nowMs = 1_000),
        )
        TextPipeline.process("template bug report", pro, interactive = true, state = state, nowMs = 0)
        val late = TextPipeline.process("just talking", pro, interactive = true, state = state, nowMs = 200_000)
        assertEquals("just talking", text(late).trimEnd('.').lowercase())
    }

    @Test fun templatesAreIgnoredWithoutPro() =
        assertTrue(TextPipeline.process("template bug report", free, interactive = true) is Spoken.Text)

    @Test fun emptyTextStaysEmpty() = assertEquals(Spoken.Text(""), TextPipeline.process("", pro, interactive = true))

    @Test fun profileOptionsAreReadFromTheTextAndFalseMeansOff() {
        val flags = AppProfiles.optionsFor(AppProfiles.parseLines("com.notes => cleanup=off"), "com.notes")
        assertFalse(flags.getValue("cleanup"))
    }
}
