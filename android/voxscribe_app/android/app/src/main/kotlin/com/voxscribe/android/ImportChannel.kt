package com.voxscribe.android

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.provider.DocumentsContract
import android.provider.OpenableColumns
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel

/**
 * Lets the Flutter import screen transcribe audio and video files.
 *
 * - One file (free): pick it, get the text and captions back, then save
 *   either one wherever the user chooses.
 * - A folder: every audio and video file in it gets a caption and/or text
 *   file saved next to it, never overwriting one that is there. Free users
 *   get [FREE_FOLDER_RUNS] runs, then folders need Pro (one file stays free).
 *
 * Uses Android's own pickers, so the app needs no storage permission and only
 * sees what the user picks. Progress goes out on an event channel.
 */
class ImportChannel(private val activity: Activity) :
    MethodChannel.MethodCallHandler, EventChannel.StreamHandler {

    private val main = Handler(Looper.getMainLooper())
    private var events: EventChannel.EventSink? = null
    private var pending: MethodChannel.Result? = null
    private var pendingCall: MethodCall? = null
    private var worker: FileTranscriber? = null

    fun register(messenger: BinaryMessenger) {
        MethodChannel(messenger, METHOD_CHANNEL).setMethodCallHandler(this)
        EventChannel(messenger, EVENT_CHANNEL).setStreamHandler(this)
    }

    override fun onListen(arguments: Any?, sink: EventChannel.EventSink) {
        events = sink
    }

    override fun onCancel(arguments: Any?) {
        events = null
    }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "folderStatus" -> result.success(
                mapOf("pro" to LicenseStore.isPro(activity), "runsLeft" to folderRunsLeft(activity)),
            )
            "cancel" -> {
                worker?.cancelled = true
                result.success(null)
            }
            "transcribeFile" -> pick(call, result, REQUEST_FILE) {
                Intent(Intent.ACTION_OPEN_DOCUMENT)
                    .addCategory(Intent.CATEGORY_OPENABLE)
                    .setType("*/*")
                    .putExtra(Intent.EXTRA_MIME_TYPES, arrayOf("audio/*", "video/*"))
            }
            "transcribeFolder" -> {
                if (!LicenseStore.isPro(activity) && folderRunsLeft(activity) <= 0) {
                    result.error("pro", "Transcribing a whole folder needs Pro. One file at a time stays free.", null)
                    return
                }
                pick(call, result, REQUEST_FOLDER) { Intent(Intent.ACTION_OPEN_DOCUMENT_TREE) }
            }
            "save" -> pick(call, result, REQUEST_SAVE) {
                Intent(Intent.ACTION_CREATE_DOCUMENT)
                    .addCategory(Intent.CATEGORY_OPENABLE)
                    .setType(call.argument<String>("mime") ?: "text/plain")
                    .putExtra(Intent.EXTRA_TITLE, call.argument<String>("name") ?: "transcript.txt")
            }
            else -> result.notImplemented()
        }
    }

    private fun pick(call: MethodCall, result: MethodChannel.Result, request: Int, intent: () -> Intent) {
        if (pending != null) {
            result.error("busy", "The file picker is already open.", null)
            return
        }
        pending = result
        pendingCall = call
        try {
            activity.startActivityForResult(intent(), request)
        } catch (e: Exception) {
            pending = null
            pendingCall = null
            result.error("no_picker", "Could not open the file picker.", e.message)
        }
    }

    /** Called from MainActivity. True when the result was ours. */
    fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?): Boolean {
        if (requestCode !in setOf(REQUEST_FILE, REQUEST_FOLDER, REQUEST_SAVE)) return false
        val result = pending ?: return true
        val call = pendingCall
        pending = null
        pendingCall = null
        val uri = data?.data
        if (resultCode != Activity.RESULT_OK || uri == null || call == null) {
            result.success(null)
            return true
        }
        when (requestCode) {
            REQUEST_FILE -> runFile(uri, result)
            REQUEST_FOLDER -> runFolder(uri, call, result)
            REQUEST_SAVE -> try {
                activity.contentResolver.openOutputStream(uri, "wt")!!.use {
                    it.write(call.argument<String>("text").orEmpty().toByteArray(Charsets.UTF_8))
                }
                result.success(displayName(activity, uri))
            } catch (e: Exception) {
                result.error("io", "Could not save the file.", e.message)
            }
        }
        return true
    }

    private fun runFile(uri: Uri, result: MethodChannel.Result) {
        val name = displayName(activity, uri) ?: "recording"
        val transcriber = FileTranscriber(activity).also { worker = it }
        Thread {
            try {
                val transcript = transcriber.transcribe(uri) { at, length -> progress(name, at, length, 0, 1) }
                main.post {
                    result.success(mapOf("name" to name, "text" to transcript.text, "srt" to transcript.srt))
                }
            } catch (e: ImportCancelled) {
                main.post { result.success(null) }
            } catch (e: Throwable) {
                main.post { result.error("failed", "Could not transcribe $name.", e.message) }
            } finally {
                worker = null
            }
        }.start()
    }

    private fun runFolder(tree: Uri, call: MethodCall, result: MethodChannel.Result) {
        val wantSrt = call.argument<Boolean>("srt") != false
        val wantTxt = call.argument<Boolean>("txt") == true
        val pro = LicenseStore.isPro(activity)
        if (!pro) useFolderRun(activity)
        val transcriber = FileTranscriber(activity).also { worker = it }
        Thread {
            var done = 0
            var failed = 0
            val saved = mutableListOf<String>()
            try {
                val folder = DocumentsContract.buildDocumentUriUsingTree(tree, DocumentsContract.getTreeDocumentId(tree))
                val children = listChildren(tree)
                val taken = children.map { it.name.lowercase() }.toMutableSet()
                val media = children.filter { it.mime.startsWith("audio/") || it.mime.startsWith("video/") }
                media.forEachIndexed { index, file ->
                    if (transcriber.cancelled) throw ImportCancelled()
                    try {
                        progress(file.name, 0.0, 0.0, index, media.size)
                        val transcript = transcriber.transcribe(file.uri) { at, length ->
                            progress(file.name, at, length, index, media.size)
                        }
                        if (wantSrt) saved.add(write(folder, file.name, "srt", "application/x-subrip", transcript.srt, taken))
                        if (wantTxt) saved.add(write(folder, file.name, "txt", "text/plain", transcript.text, taken))
                        done++
                    } catch (e: ImportCancelled) {
                        throw e
                    } catch (e: Throwable) {
                        failed++
                    }
                }
                main.post {
                    result.success(
                        mapOf("done" to done, "failed" to failed, "total" to media.size, "saved" to saved, "cancelled" to false),
                    )
                }
            } catch (e: ImportCancelled) {
                main.post {
                    result.success(mapOf("done" to done, "failed" to failed, "total" to -1, "saved" to saved, "cancelled" to true))
                }
            } catch (e: Throwable) {
                main.post { result.error("failed", "Could not read that folder.", e.message) }
            } finally {
                worker = null
            }
        }.start()
    }

    private var lastProgressAt = 0L

    /** At most a few updates a second; a decoder hands out hundreds of blocks per second. */
    private fun progress(name: String, atSec: Double, lengthSec: Double, index: Int, total: Int) {
        val now = android.os.SystemClock.elapsedRealtime()
        if (atSec > 0 && now - lastProgressAt < 250) return
        lastProgressAt = now
        val event = mapOf("name" to name, "at" to atSec, "length" to lengthSec, "index" to index, "total" to total)
        main.post { events?.success(event) }
    }

    private data class Child(val uri: Uri, val name: String, val mime: String)

    private fun listChildren(tree: Uri): List<Child> {
        val children = DocumentsContract.buildChildDocumentsUriUsingTree(tree, DocumentsContract.getTreeDocumentId(tree))
        val columns = arrayOf(
            DocumentsContract.Document.COLUMN_DOCUMENT_ID,
            DocumentsContract.Document.COLUMN_DISPLAY_NAME,
            DocumentsContract.Document.COLUMN_MIME_TYPE,
        )
        val out = mutableListOf<Child>()
        activity.contentResolver.query(children, columns, null, null, null)?.use { c ->
            while (c.moveToNext()) {
                val id = c.getString(0)
                out.add(Child(DocumentsContract.buildDocumentUriUsingTree(tree, id), c.getString(1).orEmpty(), c.getString(2).orEmpty()))
            }
        }
        return out.sortedBy { it.name.lowercase() }
    }

    /** Writes next to the source file under a name nobody has taken. Returns that name. */
    private fun write(folder: Uri, source: String, extension: String, mime: String, text: String, taken: MutableSet<String>): String {
        val name = Captions.freeName(source, extension, taken)
        val doc = DocumentsContract.createDocument(activity.contentResolver, folder, mime, name)
            ?: throw IllegalStateException("could not create $name")
        activity.contentResolver.openOutputStream(doc, "wt")!!.use { it.write(text.toByteArray(Charsets.UTF_8)) }
        // The provider may adjust the name (some add their own extension).
        val actual = displayName(activity, doc) ?: name
        taken.add(actual.lowercase())
        taken.add(name.lowercase())
        return actual
    }

    companion object {
        private const val METHOD_CHANNEL = "com.voxscribe.android/import"
        private const val EVENT_CHANNEL = "com.voxscribe.android/import_progress"
        private const val REQUEST_FILE = 4301
        private const val REQUEST_FOLDER = 4302
        private const val REQUEST_SAVE = 4303
        const val FREE_FOLDER_RUNS = 2
        private const val PREFS = "voxscribe_import"
        private const val KEY_RUNS = "folder_runs_used"

        fun folderRunsLeft(context: Context): Int {
            val used = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getInt(KEY_RUNS, 0)
            return (FREE_FOLDER_RUNS - used).coerceAtLeast(0)
        }

        private fun useFolderRun(context: Context) {
            val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            prefs.edit().putInt(KEY_RUNS, prefs.getInt(KEY_RUNS, 0) + 1).apply()
        }

        fun displayName(context: Context, uri: Uri): String? =
            runCatching {
                context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c ->
                    if (c.moveToFirst()) c.getString(0) else null
                }
            }.getOrNull()
    }
}
