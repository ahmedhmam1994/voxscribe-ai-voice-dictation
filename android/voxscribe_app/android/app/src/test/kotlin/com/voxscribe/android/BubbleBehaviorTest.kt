package com.voxscribe.android

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class FieldSafetyTest {

    @Test
    fun aPasswordFlagAloneMakesAFieldSensitive() {
        assertTrue(FieldSafety.isSensitive(isPassword = true, inputType = 0))
    }

    @Test
    fun everyPasswordInputTypeIsSensitive() {
        assertTrue(FieldSafety.isSensitive(false, 0x81))  // text password
        assertTrue(FieldSafety.isSensitive(false, 0x91))  // text visible password
        assertTrue(FieldSafety.isSensitive(false, 0xE1))  // web password
        assertTrue(FieldSafety.isSensitive(false, 0x12))  // numeric password (a PIN)
    }

    @Test
    fun ordinaryFieldsAreNotSensitive() {
        assertFalse(FieldSafety.isSensitive(false, 0x1))      // plain text
        assertFalse(FieldSafety.isSensitive(false, 0x20001))  // multi line text
        assertFalse(FieldSafety.isSensitive(false, 0x21))     // email address
        assertFalse(FieldSafety.isSensitive(false, 0xB1))     // person name
        assertFalse(FieldSafety.isSensitive(false, 0x2))      // number
        assertFalse(FieldSafety.isSensitive(false, 0))        // unknown
    }

    @Test
    fun dictationNeedsAnEditableFieldThatIsNotAPassword() {
        assertTrue(FieldSafety.allowsDictation(isEditable = true, isPassword = false, inputType = 0x1))
        assertFalse(FieldSafety.allowsDictation(isEditable = false, isPassword = false, inputType = 0x1))
        assertFalse(FieldSafety.allowsDictation(isEditable = true, isPassword = true, inputType = 0x1))
        assertFalse(FieldSafety.allowsDictation(isEditable = true, isPassword = false, inputType = 0x81))
    }
}

class HoldOrTapTest {

    @Test
    fun holdingRecordsUntilTheFingerLiftsAfterALongPress() {
        val g = HoldOrTap(tapMaxMs = 300)
        assertEquals(HoldOrTap.Action.START, g.down(0))
        assertEquals(HoldOrTap.Action.STOP, g.up(900))
        assertFalse(g.isLatched)
    }

    @Test
    fun aQuickTapKeepsRecordingUntilTheNextTap() {
        val g = HoldOrTap(tapMaxMs = 300)
        assertEquals(HoldOrTap.Action.START, g.down(0))
        assertEquals(HoldOrTap.Action.NONE, g.up(120))
        assertTrue(g.isLatched)
        assertEquals(HoldOrTap.Action.STOP, g.down(5_000))
        assertEquals(HoldOrTap.Action.NONE, g.up(5_080))
        assertFalse(g.isLatched)
    }

    @Test
    fun theTapThatStopsNeverStartsAgain() {
        val g = HoldOrTap(tapMaxMs = 300)
        g.down(0)
        g.up(100)
        g.down(2_000)
        // the finger lifting after the stopping tap must not latch or stop anything
        assertEquals(HoldOrTap.Action.NONE, g.up(2_050))
        assertEquals(HoldOrTap.Action.START, g.down(3_000))
    }

    @Test
    fun draggingCancelsARecordingThatJustStarted() {
        val g = HoldOrTap(tapMaxMs = 300)
        assertEquals(HoldOrTap.Action.START, g.down(0))
        assertEquals(HoldOrTap.Action.CANCEL, g.dragged())
        assertEquals(HoldOrTap.Action.NONE, g.up(400))
        assertFalse(g.isLatched)
    }

    @Test
    fun draggingTheStoppingTapChangesNothing() {
        val g = HoldOrTap(tapMaxMs = 300)
        g.down(0)
        g.up(100)
        assertEquals(HoldOrTap.Action.STOP, g.down(2_000))
        assertEquals(HoldOrTap.Action.NONE, g.dragged())
    }

    @Test
    fun theSafetyTimeoutOnlyStopsATapStartedRecording() {
        val g = HoldOrTap(tapMaxMs = 300)
        assertEquals(HoldOrTap.Action.NONE, g.forceStop())
        g.down(0)
        g.up(100)
        assertEquals(HoldOrTap.Action.STOP, g.forceStop())
        assertEquals(HoldOrTap.Action.NONE, g.forceStop())
    }

    @Test
    fun resetForgetsARecordingThatFailedToStart() {
        val g = HoldOrTap(tapMaxMs = 300)
        g.down(0)
        g.reset()
        assertEquals(HoldOrTap.Action.NONE, g.up(100))
        assertFalse(g.isLatched)
    }
}

class BubblePlacementTest {

    @Test
    fun clampKeepsTheWholeButtonOnScreen() {
        val p = BubblePlacement.clamp(x = 2000, y = -50, screenW = 1080, screenH = 2400, viewW = 150, viewH = 150)
        assertEquals(930, p.x)
        assertEquals(0, p.y)
        val q = BubblePlacement.clamp(x = -40, y = 5000, screenW = 1080, screenH = 2400, viewW = 150, viewH = 150)
        assertEquals(0, q.x)
        assertEquals(2250, q.y)
    }

    @Test
    fun clampSurvivesAViewBiggerThanTheScreen() {
        val p = BubblePlacement.clamp(10, 10, screenW = 100, screenH = 100, viewW = 300, viewH = 300)
        assertEquals(0, p.x)
        assertEquals(0, p.y)
    }

    @Test
    fun snapGoesToTheNearerSideEdge() {
        assertEquals(0, BubblePlacement.snapToEdge(x = 100, screenW = 1080, viewW = 150))
        assertEquals(930, BubblePlacement.snapToEdge(x = 700, screenW = 1080, viewW = 150))
        // exactly in the middle rests on the right
        assertEquals(930, BubblePlacement.snapToEdge(x = 465, screenW = 1080, viewW = 150))
    }

    @Test
    fun snapKeepsTheButtonOffTheGestureStrip() {
        // 96 px is roughly 32 dp on a 3x phone
        assertEquals(96, BubblePlacement.snapToEdge(x = 100, screenW = 1080, viewW = 150, inset = 96))
        assertEquals(834, BubblePlacement.snapToEdge(x = 700, screenW = 1080, viewW = 150, inset = 96))
        // a button wider than the room left still stays on screen
        assertEquals(60, BubblePlacement.snapToEdge(x = 0, screenW = 100, viewW = 90, inset = 60))
    }

    @Test
    fun onlyTheBottomStripHidesTheButton() {
        assertFalse(BubblePlacement.shouldSnooze(releaseY = 1200f, screenH = 2400))
        assertFalse(BubblePlacement.shouldSnooze(releaseY = 2100f, screenH = 2400))
        assertTrue(BubblePlacement.shouldSnooze(releaseY = 2200f, screenH = 2400))
        assertFalse(BubblePlacement.shouldSnooze(releaseY = 2200f, screenH = 0))
    }
}
