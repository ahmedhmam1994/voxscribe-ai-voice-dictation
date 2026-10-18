package com.voxscribe.android

import org.junit.Assert.assertEquals
import org.junit.Test

/** Mirrors the Windows app's tests/test_modes.py. */
class ModesTest {
    @Test fun freeUsesTheGlobalModeEverywhere() =
        assertEquals("notes", Modes.modeFor("com.whatsapp", null, "notes", true, pro = false))

    @Test fun freeCannotUseCodeMode() =
        assertEquals(Modes.DEFAULT, Modes.modeFor("com.termux", null, "code", true, pro = false))

    @Test fun proSwitchesByApp() {
        assertEquals("chat", Modes.modeFor("com.whatsapp", null, Modes.DEFAULT, true, pro = true))
        assertEquals("email", Modes.modeFor("com.google.android.gm", null, Modes.DEFAULT, true, pro = true))
        assertEquals("code", Modes.modeFor("com.termux", null, Modes.DEFAULT, true, pro = true))
        assertEquals("chat", Modes.modeFor("com.Slack", null, Modes.DEFAULT, true, pro = true))
    }

    @Test fun autoSwitchOffKeepsTheGlobalMode() =
        assertEquals("email", Modes.modeFor("com.whatsapp", null, "email", false, pro = true))

    @Test fun profileModeBeatsAutoSwitch() =
        assertEquals("notes", Modes.modeFor("com.whatsapp", "notes", Modes.DEFAULT, true, pro = true))

    @Test fun profileLinesCanPickAMode() =
        assertEquals(
            mapOf("com.whatsapp" to "notes"),
            AppProfiles.parseModes("com.whatsapp => mode=notes, smart=off\ncom.x => mode=nonsense"),
        )

    @Test fun dropFinalPeriodOnlyForOneSentence() {
        assertEquals("See you at 5", Modes.dropFinalPeriod("See you at 5."))
        assertEquals("Running late. See you at 5.", Modes.dropFinalPeriod("Running late. See you at 5."))
        assertEquals("Well...", Modes.dropFinalPeriod("Well..."))
        assertEquals("Bring pens, etc.", Modes.dropFinalPeriod("Bring pens, etc."))
        assertEquals("Coming?", Modes.dropFinalPeriod("Coming?"))
    }

    @Test fun chatModeDropsTheFullStopInThePipeline() {
        val options = TextOptions(pro = true, cleanup = true, voiceCommands = false, smartFormat = false, codeDictation = false, endPeriod = false)
        assertEquals(Spoken.Text("See you at 5"), TextPipeline.process("See you at 5.", options))
    }
}
