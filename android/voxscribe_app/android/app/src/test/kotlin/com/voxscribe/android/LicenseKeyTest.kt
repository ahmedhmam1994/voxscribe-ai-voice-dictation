package com.voxscribe.android

import net.i2p.crypto.eddsa.EdDSAEngine
import net.i2p.crypto.eddsa.EdDSAPrivateKey
import net.i2p.crypto.eddsa.spec.EdDSANamedCurveTable
import net.i2p.crypto.eddsa.spec.EdDSAPrivateKeySpec
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LicenseKeyTest {
    private val spec = EdDSANamedCurveTable.getByName(EdDSANamedCurveTable.ED_25519)
    private val privateSpec = EdDSAPrivateKeySpec(ByteArray(32) { it.toByte() }, spec)
    private val publicKeyHex = privateSpec.a.toByteArray().joinToString("") { "%02x".format(it) }
    private val licenseId = ByteArray(8) { (it + 1).toByte() }

    /** Builds a key the way the key generator does, with a throwaway signing key. */
    private fun keyFor(id: ByteArray): String {
        val engine = EdDSAEngine()
        engine.initSign(EdDSAPrivateKey(privateSpec))
        engine.update(id)
        return dashed(base32(id + engine.sign()))
    }

    private fun base32(bytes: ByteArray): String {
        val alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
        val out = StringBuilder()
        var buffer = 0
        var bits = 0
        for (byte in bytes) {
            buffer = (buffer shl 8) or (byte.toInt() and 0xFF)
            bits += 8
            while (bits >= 5) {
                bits -= 5
                out.append(alphabet[(buffer shr bits) and 31])
            }
        }
        if (bits > 0) out.append(alphabet[(buffer shl (5 - bits)) and 31])
        return out.toString()
    }

    private fun dashed(text: String) = text.chunked(8).joinToString("-")

    @Test
    fun aKeySignedWithTheRightKeyIsValid() {
        assertTrue(LicenseKey.isValid(keyFor(licenseId), publicKeyHex))
    }

    @Test
    fun dashesCaseAndSpacesDoNotMatter() {
        val key = keyFor(licenseId).lowercase().replace("-", " ")
        assertTrue(LicenseKey.isValid("  $key  ", publicKeyHex))
    }

    @Test
    fun aKeyWithOneCharacterChangedIsRejected() {
        val key = keyFor(licenseId)
        val changed = (if (key[3] == 'A') "B" else "A").let { key.substring(0, 3) + it + key.substring(4) }
        assertFalse(LicenseKey.isValid(changed, publicKeyHex))
    }

    @Test
    fun aKeyForADifferentLicenseIdIsRejected() {
        val key = keyFor(licenseId)
        val otherSignature = keyFor(ByteArray(8) { 9 })
        // Same signature bytes, different id: the id part is the first 13 characters.
        val mixed = otherSignature.replace("-", "").take(13) + key.replace("-", "").drop(13)
        assertFalse(LicenseKey.isValid(mixed, publicKeyHex))
    }

    @Test
    fun aKeyIsRejectedUnderAnotherPublicKey() {
        assertFalse(LicenseKey.isValid(keyFor(licenseId)))
    }

    @Test
    fun nonsenseIsRejected() {
        assertFalse(LicenseKey.isValid("", publicKeyHex))
        assertFalse(LicenseKey.isValid("hello world", publicKeyHex))
        assertFalse(LicenseKey.isValid("ABCD-EFGH", publicKeyHex))
    }
}
