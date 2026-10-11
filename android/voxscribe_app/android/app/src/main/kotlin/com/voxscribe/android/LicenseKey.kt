package com.voxscribe.android

import net.i2p.crypto.eddsa.EdDSAEngine
import net.i2p.crypto.eddsa.EdDSAPublicKey
import net.i2p.crypto.eddsa.spec.EdDSANamedCurveTable
import net.i2p.crypto.eddsa.spec.EdDSAPublicKeySpec

/**
 * Checks a VoxScribe Pro license key without any network call.
 *
 * It is the same key the Windows app accepts: base32 of an 8 byte license id
 * followed by a 64 byte Ed25519 signature of that id, written in dash
 * separated blocks. Keys are only ever signed outside this app, so this can
 * verify a key but never make one.
 */
object LicenseKey {
    /** The public half of the signing key, shared with the Windows app. */
    const val PUBLIC_KEY_HEX = "3c99649247537fb1a3ecd9e7ba0987ee1c3bdae92b911dae9eeb58095b3e2edc"

    private const val LICENSE_ID_LENGTH = 8
    private const val SIGNATURE_LENGTH = 64
    private const val BASE32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"

    fun isValid(key: String, publicKeyHex: String = PUBLIC_KEY_HEX): Boolean {
        val raw = decode(key) ?: return false
        if (raw.size != LICENSE_ID_LENGTH + SIGNATURE_LENGTH) return false
        val licenseId = raw.copyOfRange(0, LICENSE_ID_LENGTH)
        val signature = raw.copyOfRange(LICENSE_ID_LENGTH, raw.size)
        return runCatching { verify(licenseId, signature, publicKeyHex) }.getOrDefault(false)
    }

    /** Strips dashes and spaces, then reads the rest as base32. Null if it is not base32. */
    private fun decode(key: String): ByteArray? {
        val cleaned = key.filterNot { it == '-' || it.isWhitespace() }.uppercase()
        if (cleaned.isEmpty()) return null
        val bytes = ArrayList<Byte>()
        var buffer = 0
        var bits = 0
        for (char in cleaned) {
            val value = BASE32_ALPHABET.indexOf(char)
            if (value < 0) return null
            buffer = (buffer shl 5) or value
            bits += 5
            if (bits >= 8) {
                bits -= 8
                bytes.add(((buffer shr bits) and 0xFF).toByte())
            }
        }
        return bytes.toByteArray()
    }

    private fun verify(message: ByteArray, signature: ByteArray, publicKeyHex: String): Boolean {
        val spec = EdDSANamedCurveTable.getByName(EdDSANamedCurveTable.ED_25519)
        val publicKey = EdDSAPublicKey(EdDSAPublicKeySpec(hexToBytes(publicKeyHex), spec))
        val engine = EdDSAEngine()
        engine.initVerify(publicKey)
        engine.update(message)
        return engine.verify(signature)
    }

    private fun hexToBytes(hex: String): ByteArray =
        ByteArray(hex.length / 2) { hex.substring(2 * it, 2 * it + 2).toInt(16).toByte() }
}
