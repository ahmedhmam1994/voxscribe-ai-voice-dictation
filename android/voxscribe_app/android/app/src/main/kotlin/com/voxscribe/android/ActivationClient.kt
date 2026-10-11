package com.voxscribe.android

import android.content.Context
import android.provider.Settings
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/** The answer from the activation server: whether the key was accepted, and why not. */
data class ActivationResult(val ok: Boolean, val message: String)

/**
 * Claims a license key for this phone, once, when the user unlocks Pro. The
 * server holds one Windows PC and one phone per key. After that, Pro is
 * checked offline and this is not called again.
 */
object ActivationClient {
    private const val ENDPOINT = "https://getvoxscribe.vercel.app/api/activate"
    private const val PLATFORM = "android"
    private const val TIMEOUT_MILLIS = 8000

    /** Blocks on the network, so call it off the main thread. */
    fun activate(context: Context, key: String): ActivationResult {
        val body = JSONObject()
            .put("key", key.trim())
            .put("hardware_id", deviceId(context))
            .put("platform", PLATFORM)
            .toString()
        return try {
            val connection = URL(ENDPOINT).openConnection() as HttpURLConnection
            connection.requestMethod = "POST"
            connection.connectTimeout = TIMEOUT_MILLIS
            connection.readTimeout = TIMEOUT_MILLIS
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json")
            connection.outputStream.use { it.write(body.toByteArray()) }
            val code = connection.responseCode
            val stream = if (code < 400) connection.inputStream else connection.errorStream
            val text = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
            connection.disconnect()
            parse(code, text)
        } catch (error: java.io.IOException) {
            ActivationResult(false, "Could not reach the activation server. Check your connection.")
        }
    }

    private fun parse(code: Int, text: String): ActivationResult {
        val json = runCatching { JSONObject(text) }.getOrNull()
        val message = json?.optString("message").orEmpty()
        return if (json?.optBoolean("ok") == true) {
            ActivationResult(true, message)
        } else {
            ActivationResult(false, message.ifEmpty { "Activation failed ($code)." })
        }
    }

    private fun deviceId(context: Context): String =
        Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID) ?: "unknown"
}
