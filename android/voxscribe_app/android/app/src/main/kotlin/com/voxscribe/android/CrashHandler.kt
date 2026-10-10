package com.voxscribe.android

import android.content.Context
import java.io.File
import java.io.PrintWriter
import java.io.StringWriter
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Local-only crash logging, the Android counterpart to the desktop app's
 * core/crash_reporter.py. Installed in VoxScribeApplication.onCreate() so it
 * covers crashes in any component (BubbleService, the IME, activities).
 *
 * Writes to getExternalFilesDir, which needs no runtime permission on any
 * API level (unlike the shared Downloads collection, which needs MediaStore
 * API 29+ or WRITE_EXTERNAL_STORAGE below that) -- readable afterward with
 * any file manager under
 * Internal storage/Android/data/com.voxscribe.android/files/crash_logs/
 */
object CrashHandler {

    fun install(context: Context) {
        val appContext = context.applicationContext
        val previousHandler = Thread.getDefaultUncaughtExceptionHandler()

        Thread.setDefaultUncaughtExceptionHandler { thread, throwable ->
            try {
                writeCrashLog(appContext, thread, throwable)
            } catch (_: Throwable) {
                // Never let logging itself block the crash from propagating.
            }
            previousHandler?.uncaughtException(thread, throwable)
        }
    }

    private fun writeCrashLog(context: Context, thread: Thread, throwable: Throwable) {
        val dir = File(context.getExternalFilesDir(null), "crash_logs")
        dir.mkdirs()

        val timestamp = SimpleDateFormat("yyyy-MM-dd_HH-mm-ss", Locale.US).format(Date())
        val file = File(dir, "crash_$timestamp.txt")

        val stackTrace = StringWriter().also { throwable.printStackTrace(PrintWriter(it)) }.toString()

        file.writeText(
            buildString {
                appendLine("VoxScribe Android crash report")
                appendLine("Time: $timestamp")
                appendLine("Thread: ${thread.name}")
                appendLine()
                append(stackTrace)
            }
        )
    }
}
