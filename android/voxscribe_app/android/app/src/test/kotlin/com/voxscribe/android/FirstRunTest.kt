package com.voxscribe.android

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class FirstRunTest {
    @Test
    fun timesAreSentAsRangesNeverExactSeconds() {
        assertEquals("under_2s", FirstRun.secondsBucket(1.9))
        assertEquals("2_5s", FirstRun.secondsBucket(2.0))
        assertEquals("5_15s", FirstRun.secondsBucket(14.9))
        assertEquals("over_15s", FirstRun.secondsBucket(15.0))
    }

    @Test
    fun theLoudestSampleSaysSilentQuietOrNormal() {
        assertEquals("silent", FirstRun.levelFor(0.005f))
        assertEquals("quiet", FirstRun.levelFor(0.03f))
        assertEquals("normal", FirstRun.levelFor(0.4f))
    }

    @Test
    fun modelFailuresBecomeFixedCodesNotMessages() {
        assertEquals("missing_files", FirstRun.modelCode(null, filesPresent = false))
        assertEquals("native", FirstRun.modelCode(UnsatisfiedLinkError("libx.so secret path"), filesPresent = true))
        assertEquals("memory", FirstRun.modelCode(OutOfMemoryError(), filesPresent = true))
        assertEquals("other", FirstRun.modelCode(IllegalStateException("anything"), filesPresent = true))
    }

    @Test
    fun micAndInsertFailuresBecomeFixedCodes() {
        assertEquals("denied", FirstRun.micCode(permissionGranted = false))
        assertEquals("busy", FirstRun.micCode(permissionGranted = true))
        assertEquals("service_off", FirstRun.insertCode(serviceRunning = false, focusedInputType = 1))
        assertEquals("no_field", FirstRun.insertCode(serviceRunning = true, focusedInputType = 0))
        assertEquals("unsupported_field", FirstRun.insertCode(serviceRunning = true, focusedInputType = 1))
    }

    @Test
    fun activationRepliesBecomeFixedCodes() {
        assertEquals("activated", FirstRun.activationCode(true, ""))
        assertEquals("device_limit", FirstRun.activationCode(false, "This key is already active on two phones."))
        assertEquals("bad_key", FirstRun.activationCode(false, "That key is not valid. Check for typos."))
        assertEquals("network", FirstRun.activationCode(false, "Unable to resolve host"))
        assertEquals("other", FirstRun.activationCode(false, "boom"))
    }

    @Test
    fun memoryIsARangeNotTheExactSize() {
        val gb = 1024L * 1024 * 1024
        assertEquals("under_3gb", FirstRun.ramBucket(2 * gb))
        assertEquals("3_6gb", FirstRun.ramBucket(4 * gb))
        assertEquals("over_6gb", FirstRun.ramBucket(8 * gb))
    }

    @Test
    fun aFunnelEventCarriesItsExtraPropertiesAndStaysValidJson() {
        val body = Telemetry.payload("1b2c", "1.1.4", "14", "model_failed", mapOf("code" to "native", "ram" to "3_6gb"))
        assertTrue(body.contains("\"event\":\"model_failed\""))
        assertTrue(body.contains("\"platform\":\"android\",\"code\":\"native\",\"ram\":\"3_6gb\"}}"))
    }
}
