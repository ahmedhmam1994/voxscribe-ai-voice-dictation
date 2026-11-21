package com.voxscribe.android

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Which downloaded model types each language, as measured on 21 Nov 2026 (D:\asr_trial\langs.py). */
class SpeechEngineTest {
    @Test fun arabicAndTurkishGoToNemotron() {
        assertEquals(SpeechEngine.Model.NEMOTRON, SpeechEngine.modelFor("ar"))
        // Granite could not type Turkish at all; Nemotron could.
        assertEquals(SpeechEngine.Model.NEMOTRON, SpeechEngine.modelFor("tr"))
    }

    @Test fun englishAndTheEuropeanLanguagesGoToGranite() {
        for (code in listOf("en", "fr", "es", "de", "it", "pt")) {
            assertEquals(code, SpeechEngine.Model.GRANITE, SpeechEngine.modelFor(code))
        }
    }

    @Test fun theLanguagesMatchThePicker() {
        // lib/features/dictation/domain/dictation_language.dart lists the same codes.
        assertEquals(setOf("en", "ar", "tr", "fr", "es", "de", "it", "pt"), SpeechEngine.LANGUAGES)
        assertFalse("" in SpeechEngine.LANGUAGES)
    }

    @Test fun theFlutterNamesRoundTrip() {
        for (model in SpeechEngine.Model.entries) assertEquals(model, SpeechEngine.Model.fromKey(model.key))
        assertTrue(SpeechEngine.Model.fromKey("fast") == null)
    }
}
