package com.voxscribe.android

import net.i2p.crypto.eddsa.EdDSAEngine
import net.i2p.crypto.eddsa.EdDSAPublicKey
import net.i2p.crypto.eddsa.spec.EdDSANamedCurveTable
import net.i2p.crypto.eddsa.spec.EdDSAPublicKeySpec
import java.time.LocalDate

/**
 * Checks a VoxScribe Pro license key without any network call.
 *
 * It is the same key the Windows app accepts, in one of two layouts written as
 * base32 in dash separated blocks:
 *  - perpetual, the one-time keys: an 8 byte license id and a 64 byte Ed25519
 *    signature of that id.
 *  - yearly: the id, a 2 byte expiry (days since 1970-01-01, big endian) and a
 *    signature over the id and the expiry. It works through the end of that day.
 * The length tells them apart, so every perpetual key keeps working for good.
 * Keys are only ever signed outside this app, so this can verify a key but
 * never make one. Expiry is checked against the phone's clock.
 */
object LicenseKey {
    /** The public half of the signing key, shared with the Windows app. */
    const val PUBLIC_KEY_HEX = "3c99649247537fb1a3ecd9e7ba0987ee1c3bdae92b911dae9eeb58095b3e2edc"

    private const val LICENSE_ID_LENGTH = 8
    private const val EXPIRY_LENGTH = 2
    private const val SIGNATURE_LENGTH = 64
    private const val BASE32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"

    /** A validly signed key. [expires] is null for a perpetual key. */
    private class Parsed(val expires: LocalDate?)

    private fun parse(key: String, publicKeyHex: String): Parsed? {
        val raw = decode(key) ?: return null
        val message: ByteArray
        val signature: ByteArray
        val expires: LocalDate?
        when (raw.size) {
            LICENSE_ID_LENGTH + SIGNATURE_LENGTH -> {
                message = raw.copyOfRange(0, LICENSE_ID_LENGTH)
                signature = raw.copyOfRange(LICENSE_ID_LENGTH, raw.size)
                expires = null
            }
            LICENSE_ID_LENGTH + EXPIRY_LENGTH + SIGNATURE_LENGTH -> {
                val idEnd = LICENSE_ID_LENGTH + EXPIRY_LENGTH
                message = raw.copyOfRange(0, idEnd)
                signature = raw.copyOfRange(idEnd, raw.size)
                val days = ((raw[LICENSE_ID_LENGTH].toInt() and 0xFF) shl 8) or
                    (raw[LICENSE_ID_LENGTH + 1].toInt() and 0xFF)
                expires = LocalDate.ofEpochDay(days.toLong())
            }
            else -> return null
        }
        val ok = runCatching { verify(message, signature, publicKeyHex) }.getOrDefault(false)
        return if (ok) Parsed(expires) else null
    }

    /** A validly signed key, expired or not. */
    fun isValid(key: String, publicKeyHex: String = PUBLIC_KEY_HEX): Boolean =
        parse(key, publicKeyHex) != null

    /** The last day a yearly key works, or null for a perpetual or invalid key. */
    fun expiry(key: String, publicKeyHex: String = PUBLIC_KEY_HEX): LocalDate? =
        parse(key, publicKeyHex)?.expires

    /** True if the key is a valid yearly key whose last day has passed. */
    fun isExpired(
        key: String,
        today: LocalDate = LocalDate.now(),
        publicKeyHex: String = PUBLIC_KEY_HEX,
    ): Boolean = expiry(key, publicKeyHex)?.let { today.isAfter(it) } ?: false

    /** Valid and not expired: what actually unlocks Pro. */
    fun isActive(
        key: String,
        today: LocalDate = LocalDate.now(),
        publicKeyHex: String = PUBLIC_KEY_HEX,
    ): Boolean = isValid(key, publicKeyHex) && !isExpired(key, today, publicKeyHex)

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
