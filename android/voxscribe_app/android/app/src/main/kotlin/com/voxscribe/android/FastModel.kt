package com.voxscribe.android

import android.content.Context
import java.io.File
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

/**
 * The optional English fast model: NVIDIA Parakeet 110M (int8), about 131 MB.
 * It is not bundled; the user downloads it from Settings. It decodes several
 * times faster than the bundled Whisper Base and is more accurate on English,
 * but it only speaks English, so Whisper stays for Arabic and mixed speech.
 *
 * The files are checked by size and SHA-256 before they are used, and a failed
 * or cancelled download leaves nothing half-written behind.
 */
object FastModel {
    const val BASE_URL =
        "https://github.com/ahmedhmam1994/voxscribe-ai-voice-dictation/releases/download/models-1"
    const val MODEL_FILE = "model.int8.onnx"
    const val TOKENS_FILE = "tokens.txt"
    const val MODEL_BYTES = 131_652_171L
    const val TOKENS_BYTES = 9_953L
    const val MODEL_SHA256 = "9177a9146cf32ee0cc8152276ef95116f312018d316be37ccf57f7efea81fc1a"
    const val TOKENS_SHA256 = "450e56bd2f036fe5b6aa821865838cc5aa9d8b0106134ce9a9ba0664abe6cd10"

    @Volatile private var downloading = false
    @Volatile private var percent = 0
    @Volatile private var error: String? = null
    @Volatile private var cancelled = false

    fun dir(context: Context) = File(context.filesDir, "models/parakeet-110m")

    fun isInstalled(context: Context): Boolean {
        val d = dir(context)
        return File(d, MODEL_FILE).length() == MODEL_BYTES && File(d, TOKENS_FILE).length() == TOKENS_BYTES
    }

    /** True when the user chose the fast model and its files are present. */
    fun isSelected(context: Context): Boolean =
        SettingsStore.speechModel(context) == SettingsStore.MODEL_FAST && isInstalled(context)

    fun status(context: Context): Map<String, Any?> = mapOf(
        "installed" to isInstalled(context),
        "selected" to isSelected(context),
        "downloading" to downloading,
        "percent" to percent,
        "error" to error,
        "megabytes" to (MODEL_BYTES / 1_000_000).toInt(),
    )

    fun cancel() {
        cancelled = true
    }

    /** Starts the download on its own thread. Does nothing when one is already running. */
    @Synchronized
    fun download(context: Context, onFinished: () -> Unit = {}) {
        if (downloading) return
        val app = context.applicationContext
        downloading = true
        cancelled = false
        percent = 0
        error = null
        Thread {
            try {
                val d = dir(app).apply { mkdirs() }
                fetch(app, "$BASE_URL/$TOKENS_FILE", File(d, TOKENS_FILE), TOKENS_BYTES, TOKENS_SHA256, 0, 1)
                fetch(app, "$BASE_URL/$MODEL_FILE", File(d, MODEL_FILE), MODEL_BYTES, MODEL_SHA256, 1, 99)
                percent = 100
                FirstRun.feature(app, "fast_model")
            } catch (e: Exception) {
                error = if (cancelled) "Cancelled." else (e.message ?: "The download failed.")
                dir(app).deleteRecursively()
            } finally {
                downloading = false
                onFinished()
            }
        }.start()
    }

    fun delete(context: Context) {
        SettingsStore.setSpeechModel(context, SettingsStore.MODEL_BASE)
        dir(context).deleteRecursively()
    }

    private fun fetch(
        context: Context,
        url: String,
        target: File,
        expectedBytes: Long,
        expectedSha: String,
        percentFrom: Int,
        percentSpan: Int,
    ) {
        if (target.length() == expectedBytes && sha256(target) == expectedSha) return
        val part = File(target.path + ".part")
        val conn = URL(url).openConnection() as HttpURLConnection
        conn.connectTimeout = 15_000
        conn.readTimeout = 30_000
        conn.instanceFollowRedirects = true
        try {
            if (conn.responseCode != 200) throw IllegalStateException("The download server answered ${conn.responseCode}.")
            NetworkLog.record(context, "Download the English fast model", url, "Nothing about you. A plain file request.")
            val digest = MessageDigest.getInstance("SHA-256")
            var done = 0L
            conn.inputStream.use { input ->
                FileOutputStream(part).use { out ->
                    val buffer = ByteArray(64 * 1024)
                    while (true) {
                        if (cancelled) throw IllegalStateException("Cancelled.")
                        val n = input.read(buffer)
                        if (n < 0) break
                        out.write(buffer, 0, n)
                        digest.update(buffer, 0, n)
                        done += n
                        percent = percentFrom + (done * percentSpan / expectedBytes).toInt().coerceAtMost(percentSpan)
                    }
                }
            }
            if (done != expectedBytes) throw IllegalStateException("The file arrived incomplete. Try again.")
            if (digest.digest().joinToString("") { "%02x".format(it) } != expectedSha) {
                throw IllegalStateException("The file did not match its checksum. Try again.")
            }
            if (!part.renameTo(target)) throw IllegalStateException("Could not save the file.")
        } finally {
            conn.disconnect()
            part.delete()
        }
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(64 * 1024)
            while (true) {
                val n = input.read(buffer)
                if (n < 0) break
                digest.update(buffer, 0, n)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }
}
