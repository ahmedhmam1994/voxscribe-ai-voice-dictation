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
        assertEquals(
            setOf(
                "en", "fr", "es", "de", "it", "pt",
                "ar", "tr", "nl", "ru", "uk", "hi", "ja", "ko", "zh", "vi", "pl", "cs", "sk", "fi", "hu",
            ),
            SpeechEngine.LANGUAGES,
        )
        // Measured too weak on 21 Nov 2026: left out.
        for (code in listOf("sv", "da", "nb", "ro", "bg", "hr", "et", "he")) assertFalse(code, code in SpeechEngine.LANGUAGES)
        assertFalse("" in SpeechEngine.LANGUAGES)
    }

    @Test fun theFlutterNamesRoundTrip() {
        for (model in SpeechEngine.Model.entries) assertEquals(model, SpeechEngine.Model.fromKey(model.key))
        assertTrue(SpeechEngine.Model.fromKey("fast") == null)
    }

    @Test fun theNewLanguagesGoToNemotron() {
        for (code in listOf("nl", "ru", "uk", "hi", "ja", "ko", "zh", "vi", "pl", "cs", "sk", "fi", "hu")) {
            assertEquals(code, SpeechEngine.Model.NEMOTRON, SpeechEngine.modelFor(code))
        }
    }

    @Test fun eachLanguageEndsWithItsOwnMark() {
        assertEquals("今天火车晚点了所以我会晚一点回家。", SentenceFix.fix("今天火车晚点了所以我会晚一点回家", fullStop = SpeechEngine.fullStop("zh")))
        assertEquals("はい", SentenceFix.fix("はい", fullStop = SpeechEngine.fullStop("ja")))
        assertEquals("कृपया मुझे रेस्टोरेंट का पता भेज दो।", SentenceFix.fix("कृपया मुझे रेस्टोरेंट का पता भेज दो", fullStop = SpeechEngine.fullStop("hi")))
        assertEquals("Пожалуйста, купи хлеб и молоко.", SentenceFix.fix("Пожалуйста, купи хлеб и молоко", fullStop = SpeechEngine.fullStop("ru")))
        assertEquals("今天火车晚点了", Modes.dropFinalPeriod("今天火车晚点了。"))
        assertTrue(SpeechEngine.writesWithoutSpaces("ja") && SpeechEngine.writesWithoutSpaces("zh"))
        assertFalse(SpeechEngine.writesWithoutSpaces("ko"))
    }

    @Test fun chineseAndJapaneseGetTheirOwnPunctuation() {
        // What Nemotron wrote on the phone, 21 Nov 2026.
        assertEquals("今天火车晚点了，所以我会晚一点回家。", SpeechEngine.cjkPunctuation("今天火车晚点了, 所以我会晚一点回家。", "zh"))
        assertEquals("你能把餐厅的地址发给我吗？", SpeechEngine.cjkPunctuation("你能把餐厅的地址发给我吗?", "zh"))
        assertEquals("はい、わかりました", SpeechEngine.cjkPunctuation("はい, わかりました", "ja"))
        // An English name keeps its spaces, other languages are untouched.
        assertEquals("我用 iPhone 15，很好。", SpeechEngine.cjkPunctuation("我用 iPhone 15, 很好。", "zh"))
        assertEquals("Hi, there?", SpeechEngine.cjkPunctuation("Hi, there?", "ru"))
    }

    @Test fun englishFillersAreOnlyRemovedFromEnglish() {
        assertEquals("Wir treffen uns um 8 Uhr", TranscriptCleanup.clean("wir treffen uns um 8 Uhr", english = false))
        assertEquals("We meet at 8", TranscriptCleanup.clean("um we meet at 8"))
    }
}
