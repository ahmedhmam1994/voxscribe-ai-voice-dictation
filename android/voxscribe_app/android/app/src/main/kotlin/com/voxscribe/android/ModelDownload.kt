package com.voxscribe.android

import android.content.Context
import java.io.File
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

/** One file of an optional model: its name, its exact size and its SHA-256. */
class ModelFile(val name: String, val bytes: Long, val sha256: String)

/**
 * An optional model the user downloads from Settings. The files are checked by
 * size and SHA-256 before they are used, and a failed or cancelled download
 * leaves nothing half-written behind.
 */
class ModelDownload(
    private val folder: String,
    private val baseUrl: String,
    val files: List<ModelFile>,
    /** What the privacy log calls the request, for example "Download the main English model". */
    private val logName: String,
    /** The fixed name the first-use ping sends (see [FirstRun.feature]). */
    private val feature: String,
) {
    @Volatile private var downloading = false
    @Volatile private var percent = 0
    @Volatile private var error: String? = null
    @Volatile private var cancelled = false

    private val totalBytes = files.sumOf { it.bytes }

    fun dir(context: Context) = File(context.filesDir, "models/$folder")

    fun file(context: Context, name: String) = File(dir(context), name)

    fun isInstalled(context: Context): Boolean =
        files.all { file(context, it.name).length() == it.bytes }

    fun status(context: Context, extra: Map<String, Any?> = emptyMap()): Map<String, Any?> = mapOf(
        "installed" to isInstalled(context),
        "downloading" to downloading,
        "percent" to percent,
        "error" to error,
        "megabytes" to ((totalBytes + 500_000) / 1_000_000).toInt(),
    ) + extra

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
                dir(app).mkdirs()
                var before = 0L
                for (f in files) {
                    fetch(app, f, before)
                    before += f.bytes
                }
                percent = 100
                FirstRun.feature(app, feature)
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
        dir(context).deleteRecursively()
    }

    private fun fetch(context: Context, f: ModelFile, before: Long) {
        val target = file(context, f.name)
        if (target.length() == f.bytes && sha256(target) == f.sha256) return
        val part = File(target.path + ".part")
        val url = "$baseUrl/${f.name}"
        val conn = URL(url).openConnection() as HttpURLConnection
        conn.connectTimeout = 15_000
        conn.readTimeout = 30_000
        conn.instanceFollowRedirects = true
        try {
            if (conn.responseCode != 200) throw IllegalStateException("The download server answered ${conn.responseCode}.")
            NetworkLog.record(context, logName, url, "Nothing about you. A plain file request.")
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
                        percent = ((before + done.coerceAtMost(f.bytes)) * 99 / totalBytes).toInt()
                    }
                }
            }
            if (done != f.bytes) throw IllegalStateException("The file arrived incomplete. Try again.")
            if (digest.digest().joinToString("") { "%02x".format(it) } != f.sha256) {
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
