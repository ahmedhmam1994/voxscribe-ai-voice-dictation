package com.voxscribe.android

import android.app.Activity
import android.content.Intent
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel

/** Lets the Flutter Notes page read, add, delete and share the notes inbox. */
class NotesChannel(private val activity: Activity) : MethodChannel.MethodCallHandler {

    fun register(messenger: BinaryMessenger) {
        MethodChannel(messenger, CHANNEL_NAME).setMethodCallHandler(this)
    }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "getNotes" -> result.success(NotesStore.all(activity).map(::toMap))
            "addNote" -> {
                val note = NotesStore.add(activity, call.argument<String>("text").orEmpty())
                if (note != null) FirstRun.feature(activity, "notes_inbox")
                result.success(note?.let(::toMap))
            }
            "deleteNote" -> {
                call.argument<Number>("id")?.toLong()?.let { NotesStore.delete(activity, it) }
                result.success(null)
            }
            "clear" -> {
                NotesStore.clear(activity)
                result.success(null)
            }
            "markdown" -> result.success(NotesStore.markdown(NotesStore.all(activity)))
            "share" -> {
                val text = NotesStore.markdown(NotesStore.all(activity))
                val send = Intent(Intent.ACTION_SEND).apply {
                    type = "text/markdown"
                    putExtra(Intent.EXTRA_SUBJECT, "VoxScribe Inbox")
                    putExtra(Intent.EXTRA_TEXT, text)
                }
                activity.startActivity(Intent.createChooser(send, null))
                result.success(null)
            }
            else -> result.notImplemented()
        }
    }

    private fun toMap(note: Note) = mapOf("id" to note.id, "text" to note.text, "at" to note.atMillis)

    private companion object {
        const val CHANNEL_NAME = "com.voxscribe.android/notes"
    }
}
