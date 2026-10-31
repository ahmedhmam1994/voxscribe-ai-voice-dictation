package com.voxscribe.android

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Term packs, spoken formats and Teach your voice are ports of the Windows modules, so these mirror its tests. */
private fun pack(id: String): TermPacks.Pack = TermPacks.parse(File("src/main/assets/packs/$id.txt").readText())

private val MEDICAL = pack("medical")
private val LEGAL = pack("legal")
private val BUSINESS = pack("business")
private val ALL = listOf(MEDICAL, LEGAL, BUSINESS)
private val ALL_TERMS = TermPacks.combinedTerms(ALL)
private val ALL_FUZZY = TermPacks.combinedFuzzy(ALL)

class SequenceMatcherTest {
    @Test fun ratioMatchesDifflib() {
        assertEquals(1.0, SequenceMatcher.ratio("abc", "abc"), 1e-9)
        assertEquals(0.75, SequenceMatcher.ratio("abcd", "bcde"), 1e-9)
        assertEquals(0.0, SequenceMatcher.ratio("abc", "xyz"), 1e-9)
        // difflib.SequenceMatcher(None, "lisinipril", "lisinopril").ratio() == 0.9
        assertEquals(0.9, SequenceMatcher.ratio("lisinipril", "lisinopril"), 1e-9)
    }

    @Test fun matchingBlocksEndWithAMarker() {
        val blocks = SequenceMatcher(listOf("a", "b", "x", "c"), listOf("a", "b", "c")).matchingBlocks
        assertEquals(
            listOf(SequenceMatcher.Block(0, 0, 2), SequenceMatcher.Block(3, 2, 1), SequenceMatcher.Block(4, 3, 0)),
            blocks,
        )
    }
}

class TermPacksTest {
    private fun med(text: String) = TermPacks.correct(text, MEDICAL.terms, MEDICAL.fuzzy)
    private fun all(text: String) = TermPacks.correct(text, ALL_TERMS, ALL_FUZZY)

    @Test fun builtinPacksAreNotEmpty() {
        assertTrue(MEDICAL.terms.size > 200)
        assertTrue(LEGAL.terms.size > 150)
        assertTrue(BUSINESS.terms.size > 150)
    }

    @Test fun parseSkipsNotesBlanksAndRepeats() {
        val text = Char(0xFEFF) + listOf("# note", "", "MRI", "  habeas   corpus ", "mri", "x".repeat(80), "").joinToString("\n")
        assertEquals(listOf("MRI", "habeas corpus"), TermPacks.parse(text).terms)
    }

    @Test fun parseReadsFuzzySections() {
        val parsed = TermPacks.parse(listOf("a", "# fuzzy: on", "rarex", "# fuzzy: off", "common").joinToString("\n"))
        assertEquals(listOf("a", "rarex", "common"), parsed.terms)
        assertEquals(listOf("rarex"), parsed.fuzzy)
    }

    @Test fun medicalCorrections() {
        val cases = listOf(
            "the mri showed nothing" to "the MRI showed nothing",
            "Started on met formin today" to "Started on metformin today",
            "She takes lisinipril daily" to "She takes lisinopril daily",
            "Hypertension is common" to "Hypertension is common",
            "a myocardial infarction" to "a myocardial infarction",
            "an Ecg was done" to "an ECG was done",
            "I started metorfumin and lezenobril." to "I started metformin and lisinopril.",
            "apixiban and clopidogril" to "apixaban and clopidogrel",
            "started metformin and lezenobrel." to "started metformin and lisinopril.",
        )
        for ((heard, expected) in cases) assertEquals(heard, expected, med(heard))
    }

    @Test fun startOfSentenceCapitalIsKeptForLowercaseTerms() {
        assertEquals("Metformin helps.", TermPacks.correct("Metformin helps.", MEDICAL.terms))
        assertEquals("Metformin helps.", TermPacks.correct("Met formin helps.", MEDICAL.terms))
    }

    @Test fun capitalInsideASentenceIsLowered() {
        assertEquals("We gave azithromycin today.", TermPacks.correct("We gave Azithromycin today.", MEDICAL.terms))
        assertEquals("Done. Azithromycin next.", TermPacks.correct("Done. Azithromycin next.", MEDICAL.terms))
        assertEquals("Plan:\nAzithromycin daily", TermPacks.correct("Plan:\nAzithromycin daily", MEDICAL.terms))
    }

    @Test fun phraseCasing() {
        assertEquals("he filed a habeas corpus petition", TermPacks.correct("he filed a habeas corpus petition", LEGAL.terms))
        assertEquals("sign the NDA today", TermPacks.correct("sign the nda today", LEGAL.terms))
        assertEquals("EBITDA grew, EBITDA is up", TermPacks.correct("EBITDA grew, ebitda is up", BUSINESS.terms))
    }

    @Test fun ordinarySentencesAreLeftAlone() {
        val sentences = listOf(
            "I will be in the office or at home, it does not matter.",
            "She said palpitation was the problem and the answer was simple.",
            "We bid on the bun and walked to the er clinic or the operating room.",
            "Please send the report and call me back about the meeting.",
            "The safe is in Sam's room at the tam hotel.",
        )
        for (sentence in sentences) assertEquals(sentence, TermPacks.correct(sentence, ALL_TERMS))
    }

    @Test fun shortWordsAreNeverFuzzyMatched() =
        assertEquals("the stroke was mild", TermPacks.correct("the stroke was mild", listOf("stroker"), listOf("stroker")))

    @Test fun arabicTextIsUntouched() = assertEquals("هذا اجتماع مهم", TermPacks.correct("هذا اجتماع مهم", MEDICAL.terms))

    @Test fun nothingToDoWithoutTerms() {
        assertEquals("anything", TermPacks.correct("anything", emptyList()))
        assertEquals("", TermPacks.correct("", listOf("MRI")))
    }

    @Test fun fuzzyRepairOnlyReachesMarkedDrugNames() {
        assertTrue("metformin" in ALL_FUZZY)
        assertFalse("depression" in ALL_FUZZY || "litigation" in ALL_FUZZY)
        for (sentence in listOf(
            "Her expression showed relief and the complaints stopped.",
            "The evaluation and mitigation plan covers permission and discovery.",
            "The valuation of the contract depends on the validation step.",
        )) {
            assertEquals(sentence, all(sentence))
        }
    }

    @Test fun withoutFuzzyTermsMisspellingsStay() = assertEquals("lisinipril", TermPacks.correct("lisinipril", MEDICAL.terms))

    @Test fun secondRoundCorrections() {
        val cases = listOf(
            "a chest X ray today" to "a chest X-ray today",
            "tracking C A C and ARR" to "tracking CAC and ARR",
            "ordered a C B C" to "ordered a CBC",
            "given amoxillin daily" to "given amoxicillin daily",
            "discuss the indomcification clause" to "discuss the indemnification clause",
            "a laparoscopy and a colonoscopy" to "a laparoscopy and a colonoscopy",
            "she had a colonoscopi" to "she had a colonoscopy",
            "on atrovastatine daily" to "on atorvastatin daily",
        )
        for ((heard, expected) in cases) assertEquals(heard, expected, all(heard))
    }

    @Test fun packFuzzyBlocksHoldOnlyRareWords() {
        val fuzzy = ALL_FUZZY.map { it.lowercase() }.toSet()
        assertTrue(fuzzy.containsAll(listOf("colonoscopy", "indemnification", "metformin")))
        assertTrue(fuzzy.intersect(setOf("depression", "litigation", "valuation", "paracentesis")).isEmpty())
    }

    @Test fun pipelineAppliesPacksAfterReplacements() {
        val options = TextOptions(
            pro = false, cleanup = false, voiceCommands = false, smartFormat = false, codeDictation = false,
            packTerms = MEDICAL.terms, packFuzzyTerms = MEDICAL.fuzzy, spokenFormatPacks = listOf("medical"),
        )
        val spoken = TextPipeline.process("start lisinipril five milligrams twice daily", options) as Spoken.Text
        assertEquals("start lisinopril 5 mg BID", spoken.text)
    }
}

class SpokenFormatsTest {
    private fun med(text: String) = SpokenFormats.apply(text, listOf("medical"))
    private fun law(text: String) = SpokenFormats.apply(text, listOf("legal"))
    private fun biz(text: String) = SpokenFormats.apply(text, listOf("business"))

    @Test fun spokenInt() {
        val cases = mapOf(
            "one hundred and five" to 105, "a hundred" to 100, "one twenty" to 120, "one forty five" to 145,
            "two ten" to 210, "eighty" to 80, "fifty thousand" to 50000, "one" to 1, "banana" to null,
            "twenty twenty" to null,
        )
        for ((phrase, value) in cases) assertEquals(phrase, value, SpokenFormats.spokenInt(phrase))
    }

    @Test fun medicalFormats() {
        val cases = listOf(
            "blood pressure one twenty over eighty today" to "blood pressure 120/80 today",
            "one hundred and thirty over eighty five" to "130/85",
            "a hundred and ten over seventy" to "110/70",
            "five milligrams twice daily" to "5 mg BID",
            "take ten milligrams by mouth every eight hours" to "take 10 mg PO q8h",
            "two point five milligrams three times a day" to "2.5 mg TID",
            "point five milligrams as needed" to "0.5 mg PRN",
            "two hundred micrograms" to "200 mcg",
            "five hundred milliliters of saline" to "500 mL of saline",
            "oxygen saturation ninety eight percent" to "oxygen saturation 98%",
        )
        for ((spoken, written) in cases) assertEquals(spoken, written, med(spoken))
    }

    @Test fun medicalFormatsLeaveOrdinaryTextAlone() {
        for (spoken in listOf(
            "one over two of the team agreed", "I walked three miles twice daily", "she took one of them",
            "the score was ten over four hundred", "fifty over thirty five",
        )) {
            assertEquals(spoken, med(spoken))
        }
    }

    @Test fun legalFormats() {
        val cases = listOf(
            "section twelve subsection b" to "section 12(b)",
            "Section twelve subsection b subsection two" to "Section 12(b)(2)",
            "see article five" to "see article 5",
            "clause four point two applies" to "clause 4.2 applies",
            "paragraph three of the agreement" to "paragraph 3 of the agreement",
            "Smith versus Jones was decided" to "Smith v. Jones was decided",
        )
        for ((spoken, written) in cases) assertEquals(spoken, written, law(spoken))
        assertEquals("cats versus dogs", law("cats versus dogs"))
    }

    @Test fun businessFormats() {
        val cases = listOf(
            "fifty thousand dollars" to "$50,000",
            "two point five million dollars" to "$2.5 million",
            "one hundred and five dollars" to "$105",
            "a budget of three million euros" to "a budget of €3 million",
            "growth of twenty percent" to "growth of 20%",
            "results for q three" to "results for Q3",
            "Q four planning" to "Q4 planning",
        )
        for ((spoken, written) in cases) assertEquals(spoken, written, biz(spoken))
    }

    @Test fun aPackOnlyFormatsItsOwnThings() {
        assertEquals("five milligrams", law("five milligrams"))
        assertEquals("section twelve", med("section twelve"))
        assertEquals("fifty thousand dollars", med("fifty thousand dollars"))
        assertEquals("five milligrams", SpokenFormats.apply("five milligrams", emptyList()))
        assertEquals("", SpokenFormats.apply("", listOf("medical", "legal", "business")))
    }

    @Test fun allPacksTogether() = assertEquals(
        "120/80 and section 9 and $50,000",
        SpokenFormats.apply(
            "one twenty over eighty and section nine and fifty thousand dollars",
            listOf("medical", "legal", "business"),
        ),
    )

    @Test fun digitsWrittenByTheSpeechModel() {
        val cases = listOf(
            "Blood pressure on 20 over 80, 5 milligrams twice daily" to "Blood pressure 120/80, 5 mg BID",
            "blood pressure one 40 over 90" to "blood pressure 140/90",
            "pressure 120 over 80 today" to "pressure 120/80 today",
            "take 10 milligrams by mouth every 8 hours" to "take 10 mg PO q8h",
            "2.5 milligrams three times a day" to "2.5 mg TID",
            "500 milliliters of saline" to "500 mL of saline",
            "oxygen saturation 98 percent" to "oxygen saturation 98%",
            "1,000 micrograms" to "1000 mcg",
        )
        for ((spoken, written) in cases) assertEquals(spoken, written, med(spoken))
        for (spoken in listOf("5 over 3 was the score", "it was on 20 over time", "20 over 80 degrees is not a pressure", "I have 5 minutes")) {
            assertEquals(spoken, med(spoken))
        }
    }

    @Test fun digitsInLawAndBusiness() {
        assertEquals("see section 12(b)", law("see section 12 subsection b"))
        assertEquals("clause 4.2 applies", law("clause 4.2 applies"))
        assertEquals("a fee of $50,000", biz("a fee of 50000 dollars"))
        assertEquals("it cost $2.5 million", biz("it cost 2.5 million dollars"))
        assertEquals("growth of 20%", biz("growth of 20 percent"))
    }
}

class VoiceTeachTest {
    private fun line(pack: String, index: Int) = VoiceTeach.SENTENCES.getValue(pack)[index]

    @Test fun everyTargetIsATermOfItsPack() {
        for ((id, lines) in VoiceTeach.SENTENCES) {
            val terms = pack(id).terms.map { it.lowercase() }.toSet()
            for (l in lines) for (target in l.terms) assertTrue("$id $target", target.lowercase() in terms)
        }
    }

    @Test fun scriptAlternatesPacks() {
        val script = VoiceTeach.buildScript(listOf("medical", "legal"), length = 6)
        assertEquals(line("medical", 0), script[0])
        assertEquals(line("legal", 0), script[1])
        assertEquals(6, script.size)
        assertEquals(3, VoiceTeach.buildScript(emptyList(), length = 3).size)
    }

    @Test fun sentenceHeardRightHasNoSlips() {
        val l = line("medical", 1)
        assertEquals(emptyList<VoiceTeach.Slip>(), VoiceTeach.findSlips(l.sentence, l.terms, "The doctor ordered a CBC and HbA1c and a chest X ray."))
    }

    @Test fun misheardTermsBecomeSlips() {
        val l = line("medical", 4)
        assertEquals(
            listOf(VoiceTeach.Slip("levoseroxine", "levothyroxine"), VoiceTeach.Slip("hypoceroxidism", "hypothyroidism")),
            VoiceTeach.findSlips(l.sentence, l.terms, "TSH was high so we started levoseroxine for hypoceroxidism."),
        )
    }

    @Test fun multiWordTermSlip() {
        val l = line("legal", 2)
        assertEquals(
            listOf(VoiceTeach.Slip("status of the limitation", "statute of limitations")),
            VoiceTeach.findSlips(l.sentence, l.terms, "The lawyer cited habeas corpus and the status of the limitation."),
        )
    }

    @Test fun garbledOrKnownOrStopwordTextIsNotProposed() {
        val med = line("medical", 0)
        assertTrue(VoiceTeach.findSlips(med.sentence, med.terms, "Something completely different was said here.").isEmpty())
        val biz = line("business", 2)
        assertTrue(VoiceTeach.findSlips(biz.sentence, biz.terms, "We are tracking CAC and ARR and churn for the board meeting.", listOf("churn")).isEmpty())
        assertTrue(VoiceTeach.findSlips(biz.sentence, biz.terms, "We are tracking CAC and ARR and KPI for the board meeting.", listOf("KPI")).isEmpty())
        val sla = line("business", 1)
        assertTrue(VoiceTeach.findSlips(sla.sentence, sla.terms, "The client wants to renew the SLA before the end of it.").isEmpty())
        assertTrue(VoiceTeach.findSlips("A b c", listOf("b"), "").isEmpty())
    }

    @Test fun mergeCountsRepeatsAndOrdersThemFirst() {
        val merged = VoiceTeach.merge(
            listOf(
                listOf(VoiceTeach.Slip("chern", "churn")),
                listOf(VoiceTeach.Slip("kbi", "KPI"), VoiceTeach.Slip("chern", "churn")),
            ),
        )
        assertEquals(listOf(VoiceTeach.Proposal("chern", "churn", 2), VoiceTeach.Proposal("kbi", "KPI", 1)), merged)
    }
}
