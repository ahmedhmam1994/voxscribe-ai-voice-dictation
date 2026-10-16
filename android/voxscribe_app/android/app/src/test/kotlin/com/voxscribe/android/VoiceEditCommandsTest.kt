package com.voxscribe.android

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class VoiceEditCommandsTest {

    // ---- capitalize, upper and lower case

    @Test
    fun transformCommandsAreRecognisedAsWholeUtterances() {
        assertEquals(VoiceCommands.Transform.CAPITALIZE, VoiceCommands.transformCommand("Capitalize that."))
        assertEquals(VoiceCommands.Transform.CAPITALIZE, VoiceCommands.transformCommand("capitalise that"))
        assertEquals(VoiceCommands.Transform.UPPERCASE, VoiceCommands.transformCommand("All caps"))
        assertEquals(VoiceCommands.Transform.UPPERCASE, VoiceCommands.transformCommand("Make that uppercase."))
        assertEquals(VoiceCommands.Transform.LOWERCASE, VoiceCommands.transformCommand("lowercase that"))
        assertEquals(VoiceCommands.Transform.LOWERCASE, VoiceCommands.transformCommand("All lowercase!"))
    }

    @Test
    fun aSentenceThatMerelyContainsTheWordsIsStillDictation() {
        assertNull(VoiceCommands.transformCommand("please capitalize that word in the title"))
        assertNull(VoiceCommands.transformCommand("the sign said all caps and bold"))
        assertNull(VoiceCommands.transformCommand(""))
    }

    @Test
    fun capitalizeStartsEveryWordAndKeepsTheSpacing() {
        assertEquals("Bring The Notes", VoiceCommands.applyTransform("bring the notes", VoiceCommands.Transform.CAPITALIZE))
        assertEquals("A  B\nC", VoiceCommands.applyTransform("a  b\nc", VoiceCommands.Transform.CAPITALIZE))
        assertEquals("Already Capital", VoiceCommands.applyTransform("Already capital", VoiceCommands.Transform.CAPITALIZE))
    }

    @Test
    fun upperAndLowerCaseChangeTheWholeText() {
        assertEquals("HELLO, WORLD.", VoiceCommands.applyTransform("Hello, world.", VoiceCommands.Transform.UPPERCASE))
        assertEquals("hello, world.", VoiceCommands.applyTransform("Hello, World.", VoiceCommands.Transform.LOWERCASE))
    }

    // ---- a command at the end of the same sentence

    @Test
    fun aCommandAfterAPauseEndsTheSentence() {
        assertEquals(
            "Bring the notes" to VoiceCommands.Transform.UPPERCASE,
            VoiceCommands.splitTrailingTransform("Bring the notes, all caps."),
        )
        assertEquals(
            "bring the notes" to VoiceCommands.Transform.CAPITALIZE,
            VoiceCommands.splitTrailingTransform("bring the notes. Capitalize that"),
        )
        assertEquals(
            "SHOUTING" to VoiceCommands.Transform.LOWERCASE,
            VoiceCommands.splitTrailingTransform("SHOUTING, all lowercase!"),
        )
    }

    @Test
    fun theModelsUsualMishearingsCountToo() {
        assertEquals(
            "Meet me at noon" to VoiceCommands.Transform.CAPITALIZE,
            VoiceCommands.splitTrailingTransform("Meet me at noon. Capitalize Z."),
        )
        assertEquals(
            "With me, I had now" to VoiceCommands.Transform.CAPITALIZE,
            VoiceCommands.splitTrailingTransform("With me, I had now capitalized that"),
        )
        assertEquals(VoiceCommands.Transform.CAPITALIZE, VoiceCommands.transformCommand("Capitalise Z."))
    }

    @Test
    fun aQuestionOrExclamationMarkStaysWithTheSentence() {
        assertEquals(
            "Do you hear me?" to VoiceCommands.Transform.UPPERCASE,
            VoiceCommands.splitTrailingTransform("Do you hear me? All caps!"),
        )
        assertEquals(
            "Stop!" to VoiceCommands.Transform.LOWERCASE,
            VoiceCommands.splitTrailingTransform("Stop! Lowercase that."),
        )
    }

    @Test
    fun aBareKeywordNeedsAPauseAndIsNeverMidSentence() {
        assertEquals(
            "bring the notes" to VoiceCommands.Transform.UPPERCASE,
            VoiceCommands.splitTrailingTransform("bring the notes, uppercase"),
        )
        assertNull(VoiceCommands.splitTrailingTransform("we should capitalize"))
        assertNull(VoiceCommands.splitTrailingTransform("we should capitalize on this chance"))
    }

    @Test
    fun anItCommandNeedsAPauseSoOrdinarySentencesAreSafe() {
        assertNull(VoiceCommands.splitTrailingTransform("We need to capitalize it."))
        assertNull(VoiceCommands.splitTrailingTransform("you can lowercase it"))
        assertEquals(
            "Here is the title" to VoiceCommands.Transform.CAPITALIZE,
            VoiceCommands.splitTrailingTransform("Here is the title, capitalize it."),
        )
    }

    @Test
    fun theClearPhrasesCountEvenWithoutAPause() {
        assertEquals(
            "bring the notes" to VoiceCommands.Transform.UPPERCASE,
            VoiceCommands.splitTrailingTransform("bring the notes uppercase that"),
        )
        assertEquals(
            "meet me at noon" to VoiceCommands.Transform.CAPITALIZE,
            VoiceCommands.splitTrailingTransform("meet me at noon capitalize that."),
        )
    }

    @Test
    fun theBarePhrasesNeedAPauseSoOrdinaryWordsAreSafe() {
        assertNull(VoiceCommands.splitTrailingTransform("write the title in all caps"))
        assertNull(VoiceCommands.splitTrailingTransform("she typed it all lowercase"))
        assertNull(VoiceCommands.splitTrailingTransform("all caps"))
        assertNull(VoiceCommands.splitTrailingTransform(", all caps"))
        assertNull(VoiceCommands.splitTrailingTransform("capitalize that word, please"))
    }

    // ---- replace X with Y

    @Test
    fun replaceCommandSplitsIntoTheTwoPhrases() {
        assertEquals("Sam" to "Tom", VoiceCommands.replaceCommand("Replace Sam with Tom."))
        assertEquals("the battery" to "a new one", VoiceCommands.replaceCommand("replace the battery with a new one"))
    }

    @Test
    fun replaceCommandNeedsBothSides() {
        assertNull(VoiceCommands.replaceCommand("please replace it"))
        assertNull(VoiceCommands.replaceCommand("replace with"))
        assertNull(VoiceCommands.replaceCommand("replace sam with"))
    }

    @Test
    fun replaceOnlyTouchesWholeWordsAndIgnoresCase() {
        assertEquals("Meet me at one", VoiceCommands.applyReplace("Meet me at noon", "noon", "one"))
        assertEquals("Meet me at one.", VoiceCommands.applyReplace("Meet me at Noon.", "NOON", "one"))
        assertNull(VoiceCommands.applyReplace("noonish plans", "noon", "one"))
        assertNull(VoiceCommands.applyReplace("Meet me at noon", "midnight", "one"))
    }

    @Test
    fun replaceChangesEveryOccurrenceAndKeepsSymbolsAsTyped() {
        assertEquals("tea and tea", VoiceCommands.applyReplace("coffee and coffee", "coffee", "tea"))
        assertEquals("the price is \$5 \\ done", VoiceCommands.applyReplace("the price is cheap", "cheap", "\$5 \\ done"))
    }

    // ---- a replace at the end of the same sentence

    @Test
    fun aTrailingReplaceChangesTheSentenceBeforeIt() {
        assertEquals("Meet me at one", VoiceCommands.applyTrailingReplace("Meet me at noon. Replace noon with one."))
        assertEquals("meet me at one", VoiceCommands.applyTrailingReplace("meet me at noon, replace noon with one"))
        assertEquals(
            "Where is Tom?",
            VoiceCommands.applyTrailingReplace("Where is Sam? Replace Sam with Tom."),
        )
    }

    @Test
    fun aTrailingReplaceNeedsThePhraseToBeInTheSentence() {
        assertNull(VoiceCommands.applyTrailingReplace("I will replace the battery with a new one"))
        assertNull(VoiceCommands.applyTrailingReplace("Please, replace the filter with a new one"))
        assertNull(VoiceCommands.applyTrailingReplace("Meet me at noon. Replace lunch with one."))
        assertNull(VoiceCommands.applyTrailingReplace("Replace noon with one"))
        assertNull(VoiceCommands.applyTrailingReplace("Meet me at noon, replace noon with"))
    }

    // ---- send it, on its own and at the end of a sentence

    @Test
    fun sendItIsTheSendButtonAndPressEnterIsTheKey() {
        assertEquals(VoiceCommands.SendKind.SEND, VoiceCommands.sendCommand("Send it."))
        assertEquals(VoiceCommands.SendKind.SEND, VoiceCommands.sendCommand("send that"))
        assertEquals(VoiceCommands.SendKind.ENTER, VoiceCommands.sendCommand("Press enter!"))
        assertNull(VoiceCommands.sendCommand("send it to Sam"))
    }

    @Test
    fun aSendAtTheEndOfTheSentenceNeedsAPause() {
        assertEquals(
            "How are you? Are you good?" to VoiceCommands.SendKind.SEND,
            VoiceCommands.splitTrailingSend("How are you? Are you good? Send it."),
        )
        assertEquals(
            "with me I've known" to VoiceCommands.SendKind.SEND,
            VoiceCommands.splitTrailingSend("with me I've known, send it."),
        )
        assertEquals(
            "Sounds good" to VoiceCommands.SendKind.ENTER,
            VoiceCommands.splitTrailingSend("Sounds good, press enter"),
        )
        assertNull(VoiceCommands.splitTrailingSend("please send it to Sam"))
        assertNull(VoiceCommands.splitTrailingSend("Send it."))
        assertNull(VoiceCommands.splitTrailingSend(", send it"))
    }

    // ---- send it

    @Test
    fun sendItIsOnlyAWholeUtterance() {
        assertTrue(VoiceCommands.isSendCommand("Send it."))
        assertTrue(VoiceCommands.isSendCommand("press enter"))
        assertTrue(VoiceCommands.isSendCommand("Hit enter!"))
        assertFalse(VoiceCommands.isSendCommand("send it to Sam"))
        assertFalse(VoiceCommands.isSendCommand("don't send it yet"))
        assertFalse(VoiceCommands.isSendCommand(""))
    }
}

class VoiceEditPipelineTest {

    private val options = TextOptions(
        pro = false, cleanup = true, voiceCommands = true, smartFormat = false, codeDictation = false,
    )

    private fun run(raw: String, o: TextOptions = options, allowReplace: Boolean = true) =
        TextPipeline.process(raw, o, interactive = true, allowReplace = allowReplace)

    @Test
    fun transformCommandsBecomeTransformResults() {
        assertEquals(Spoken.Transform(VoiceCommands.Transform.UPPERCASE), run("All caps."))
        assertEquals(Spoken.Transform(VoiceCommands.Transform.CAPITALIZE), run("Capitalize that"))
    }

    @Test
    fun theyAreOffWhenVoiceCommandsAreOff() {
        val off = options.copy(voiceCommands = false)
        assertTrue(run("all caps", off) is Spoken.Text)
        assertTrue(run("replace sam with tom", off) is Spoken.Text)
    }

    @Test
    fun replaceKeepsTheRawWordsSoItCanFallBackToDictation() {
        val spoken = run("Replace Sam with Tom.") as Spoken.Replace
        assertEquals("Sam", spoken.from)
        assertEquals("Tom", spoken.to)
        assertEquals("Replace Sam with Tom.", spoken.raw)
    }

    @Test
    fun withReplaceSwitchedOffTheWordsAreJustTyped() {
        val spoken = run("replace the battery with a new one", allowReplace = false)
        assertEquals("Replace the battery with a new one", (spoken as Spoken.Text).text)
    }

    @Test
    fun aTrailingCommandChangesTheSentenceItIsSaidWith() {
        assertEquals("BRING THE NOTES", (run("Bring the notes, all caps.") as Spoken.Text).text)
        assertEquals("Bring The Notes", (run("bring the notes, capitalize that") as Spoken.Text).text)
        assertEquals("bring the notes", (run("Bring the notes, lowercase that") as Spoken.Text).text)
    }

    @Test
    fun aTrailingReplaceIsTypedAsTheChangedSentence() {
        assertEquals("Meet me at one", (run("Meet me at noon. Replace noon with one.") as Spoken.Text).text)
    }

    @Test
    fun aTrailingReplaceIsOffWithVoiceCommands() {
        val off = options.copy(voiceCommands = false)
        val spoken = run("Meet me at noon. Replace noon with one.", off) as Spoken.Text
        assertEquals("Meet me at noon. Replace noon with one.", spoken.text)
    }

    @Test
    fun aTrailingCommandKeepsAQuestionMark() {
        assertEquals("DO YOU HEAR ME?", (run("Do you hear me? All caps!") as Spoken.Text).text)
    }

    @Test
    fun aTrailingCommandIsOffWithVoiceCommands() {
        val off = options.copy(voiceCommands = false)
        assertEquals("Bring the notes, all caps.", (run("Bring the notes, all caps.", off) as Spoken.Text).text)
    }

    @Test
    fun aTrailingCommandAlsoWorksOutsideTheBubble() {
        val spoken = TextPipeline.process("Bring the notes, all caps.", options, interactive = false)
        assertEquals("BRING THE NOTES", (spoken as Spoken.Text).text)
    }

    @Test
    fun sendItNeedsItsOwnSwitch() {
        assertTrue(run("send it") is Spoken.Text)
        assertEquals(Spoken.Send(VoiceCommands.SendKind.SEND), run("Send it.", options.copy(sendIt = true)))
        // it works even when the other voice commands are off
        assertEquals(
            Spoken.Send(VoiceCommands.SendKind.ENTER),
            run("press enter", options.copy(voiceCommands = false, sendIt = true)),
        )
    }

    @Test
    fun aSendAtTheEndOfTheSentenceTypesItThenAsksToSend() {
        val on = options.copy(sendIt = true)
        val spoken = run("How are you? Are you good? Send it.", on) as Spoken.Text
        assertEquals("How are you? Are you good?", spoken.text)
        assertEquals(VoiceCommands.SendKind.SEND, spoken.thenSend)
    }

    @Test
    fun aSendAtTheEndNeedsTheSwitchAndTheBubble() {
        val sentence = "How are you? Send it."
        val off = run(sentence) as Spoken.Text
        assertEquals("How are you? Send it.", off.text)
        assertNull(off.thenSend)
        val outside = TextPipeline.process(sentence, options.copy(sendIt = true), interactive = false) as Spoken.Text
        assertNull(outside.thenSend)
    }

    @Test
    fun aLongerSentenceIsNeverACommand() {
        val on = options.copy(sendIt = true)
        assertTrue(run("send it to Sam tomorrow", on) is Spoken.Text)
        assertTrue(run("we need all caps on the sign", on) is Spoken.Text)
    }

    @Test
    fun nothingHappensOutsideTheBubble() {
        val spoken = TextPipeline.process("all caps", options.copy(sendIt = true), interactive = false)
        assertTrue(spoken is Spoken.Text)
    }
}
