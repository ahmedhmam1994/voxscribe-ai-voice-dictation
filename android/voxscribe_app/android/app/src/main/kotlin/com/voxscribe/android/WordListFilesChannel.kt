package com.voxscribe.android

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.provider.OpenableColumns
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel

/**
 * Saves and opens the word lists file with Android's own file picker, so the
 * app needs no storage permission: it only ever sees the one file the user picks.
 */
class WordListFilesChannel(private val activity: Activity) : MethodChannel.MethodCallHandler {

    private var pending: MethodChannel.Result? = null
    private var pendingText: String? = null

    fun register(messenger: BinaryMessenger) {
        MethodChannel(messenger, CHANNEL_NAME).setMethodCallHandler(this)
    }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "saveFile" -> {
                if (!claim(result)) return
                pendingText = call.argument<String>("text").orEmpty()
                val intent = Intent(Intent.ACTION_CREATE_DOCUMENT)
                    .addCategory(Intent.CATEGORY_OPENABLE)
                    .setType("application/json")
                    .putExtra(Intent.EXTRA_TITLE, call.argument<String>("fileName") ?: DEFAULT_NAME)
                launch(intent, REQUEST_SAVE)
            }
            "openFile" -> {
                if (!claim(result)) return
                val intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
                    .addCategory(Intent.CATEGORY_OPENABLE)
                    .setType("*/*")
                launch(intent, REQUEST_OPEN)
            }
            else -> result.notImplemented()
        }
    }

    /** Called from MainActivity. True when the result was ours. */
    fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?): Boolean {
        if (requestCode != REQUEST_SAVE && requestCode != REQUEST_OPEN) return false
        val result = pending ?: return true
        val text = pendingText
        pending = null
        pendingText = null
        val uri = data?.data
        if (resultCode != Activity.RESULT_OK || uri == null) {
            result.success(null)
            return true
        }
        try {
            if (requestCode == REQUEST_SAVE) {
                write(uri, text.orEmpty())
                result.success(displayName(uri) ?: DEFAULT_NAME)
            } else {
                result.success(read(uri))
            }
        } catch (e: TooLargeException) {
            result.error("too_large", "That file is too big to be a word list.", null)
        } catch (e: Exception) {
            val what = if (requestCode == REQUEST_SAVE) "save" else "read"
            result.error("io", "Could not $what the file.", e.message)
        }
        return true
    }

    private fun claim(result: MethodChannel.Result): Boolean {
        if (pending != null) {
            result.error("busy", "The file picker is already open.", null)
            return false
        }
        pending = result
        return true
    }

    private fun launch(intent: Intent, requestCode: Int) {
        try {
            activity.startActivityForResult(intent, requestCode)
        } catch (e: Exception) {
            val result = pending
            pending = null
            pendingText = null
            result?.error("no_picker", "Could not open the file picker.", e.message)
        }
    }

    private fun write(uri: Uri, text: String) {
        val stream = activity.contentResolver.openOutputStream(uri, "wt")
            ?: throw IllegalStateException("no output stream")
        stream.use { it.write(text.toByteArray(Charsets.UTF_8)) }
    }

    private fun read(uri: Uri): String {
        val stream = activity.contentResolver.openInputStream(uri)
            ?: throw IllegalStateException("no input stream")
        val bytes = stream.use { input ->
            val buffer = input.readNBytesCompat(MAX_BYTES + 1)
            if (buffer.size > MAX_BYTES) throw TooLargeException()
            buffer
        }
        return String(bytes, Charsets.UTF_8)
    }

    private fun java.io.InputStream.readNBytesCompat(limit: Int): ByteArray {
        val out = java.io.ByteArrayOutputStream()
        val chunk = ByteArray(8192)
        while (out.size() < limit) {
            val n = read(chunk, 0, minOf(chunk.size, limit - out.size()))
            if (n < 0) break
            out.write(chunk, 0, n)
        }
        return out.toByteArray()
    }

    private fun displayName(uri: Uri): String? =
        activity.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)
            ?.use { cursor -> if (cursor.moveToFirst()) cursor.getString(0) else null }

    private class TooLargeException : Exception()

    private companion object {
        const val CHANNEL_NAME = "com.voxscribe.android/wordlistfiles"
        const val DEFAULT_NAME = "voxscribe-word-lists.json"
        const val REQUEST_SAVE = 7301
        const val REQUEST_OPEN = 7302
        const val MAX_BYTES = 1_000_000
    }
}
