package com.voxscribe.android

import android.accessibilityservice.AccessibilityService
import android.content.ClipData
import android.content.ClipboardManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo

/**
 * Powers floating-bubble mode (see BubblePermissions.kt): an alternative to
 * switching keyboards, the same approach Wispr Flow uses on Android. Once
 * enabled, this service tracks which text field is focused and can insert
 * dictated text into it directly via AccessibilityNodeInfo, instead of
 * relying on being the active InputMethodService the way
 * VoxScribeInputMethodService.kt does.
 *
 * Phase 4 will call [insertText] via [instance] once the bubble's real
 * recording/transcription flow is wired up (today it just drives the
 * bubble's own visual state, see BubbleService.kt's TODOs).
 *
 * If a text field was already focused *before* this service was enabled
 * (or the app never fired a TYPE_VIEW_FOCUSED event VoxScribe caught),
 * [focusedNode] is stale or null -- [insertText] falls back to walking
 * `rootInActiveWindow` for whichever node reports `isFocused` in that case,
 * at the cost of a window-tree walk, but only on that fallback path, not
 * on every insertion.
 */
class VoxScribeAccessibilityService : AccessibilityService() {

    private var focusedNode: AccessibilityNodeInfo? = null

    // What VoxScribe itself last wrote into the current field, or null if
    // nothing's been dictated into it yet this focus session. Some apps
    // (confirmed on WhatsApp's message box) set their placeholder as the
    // field's literal text -- e.g. "Message" -- rather than through
    // Android's real hint API, so hintText/isShowingHintText both come back
    // empty/false and there is no way to tell placeholder from real content
    // by reading the field. Tracking our own last write sidesteps that
    // entirely: the first dictation into a field replaces whatever's
    // showing (placeholder or not), and later dictations in the same
    // session append to what we know we wrote, never to a fresh read.
    private var lastWrittenText: String? = null

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        Log.d(TAG, "VoxScribeAccessibilityService connected")
    }

    // The "missing cases" lint would otherwise flag are event types this
    // service never receives in the first place -- accessibility_service_config.xml's
    // accessibilityEventTypes only subscribes to the two handled below.
    @Suppress("SwitchIntDef")
    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        event ?: return
        when (event.eventType) {
            AccessibilityEvent.TYPE_VIEW_FOCUSED -> {
                focusedNode.recycleCompat()
                focusedNode = event.source
                lastWrittenText = null
            }

            AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED -> {
                // The window/app changed -- the previously focused node is
                // almost certainly stale now. Drop it rather than risk
                // inserting into a field that's no longer visible.
                focusedNode.recycleCompat()
                focusedNode = null
                lastWrittenText = null
            }
        }
    }

    override fun onInterrupt() {
        // Required override; nothing to clean up here specifically.
    }

    override fun onUnbind(intent: android.content.Intent?): Boolean {
        focusedNode.recycleCompat()
        focusedNode = null
        instance = null
        return super.onUnbind(intent)
    }

    /**
     * Appends [text] to the end of whichever field was last focused (not
     * cursor/selection-based -- see the comment inline for why). Must be
     * called on this service's own thread (the main thread, by Android's
     * AccessibilityService contract) -- Phase 4's caller needs to hop back
     * onto it after transcription finishes on a background thread.
     *
     * Returns false if there's no usable focused field to insert into;
     * callers should treat that as "couldn't dictate here" rather than a
     * crash-worthy error, the same way the desktop app treats a missing
     * microphone.
     */
    fun insertText(text: String): Boolean {
        var node = focusedNode
        if (node == null || !node.refresh() || !node.isEditable) {
            // Either nothing was ever tracked, the tracked view is gone, or
            // it wasn't actually an editable field -- fall back to walking
            // the current window for whichever node self-reports isFocused.
            // Covers a field that was already focused before this service
            // was enabled, or an app whose custom view never fired
            // TYPE_VIEW_FOCUSED.
            focusedNode = null
            node = findFocusedEditableNode()
            if (node == null) return false
        }

        // Cursor/selection reporting via AccessibilityNodeInfo is unreliable
        // across apps -- many chat/compose fields report selection as 0,0
        // even mid-typing rather than -1 (unknown), which previously made
        // dictated text land at the *start* of the field instead of where
        // the user actually was. Hold-to-talk dictation is almost always
        // "keep adding to what's there" anyway, so append instead of
        // trusting selection state.
        //
        // Reading node.text as "existing content" is *also* unreliable:
        // confirmed on device that WhatsApp's message box sets its
        // placeholder ("Message") as the field's literal text rather than
        // through Android's real hint API, so hintText/isShowingHintText
        // both come back empty/false -- there is no way to distinguish
        // placeholder from real content by reading the field. Tracking
        // what VoxScribe itself last wrote (see lastWrittenText) sidesteps
        // that: the first dictation into a field replaces whatever's
        // showing outright, and only a later dictation in the same
        // uninterrupted focus session appends.
        node.refresh()
        val existing = lastWrittenText ?: ""
        val newText = existing + text

        val setTextArgs = Bundle().apply {
            putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, newText)
        }
        if (node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, setTextArgs)) {
            lastWrittenText = newText
            focusedNode = node
            placeCursorAfterInsertedText(node, newText.length)
            return true
        }

        // ACTION_SET_TEXT isn't supported by every field (some WebViews
        // and non-standard custom views don't implement it) -- ACTION_PASTE
        // is the documented fallback, but it necessarily goes through the
        // clipboard, unlike the desktop app's direct-typing approach.
        // Minimized, not eliminated: the user's previous clipboard content
        // is restored shortly after, same spirit as never wanting to
        // permanently clobber it.
        return pasteFallback(node, text)
    }

    /** Depth-first search of the active window for a focused, editable node. */
    private fun findFocusedEditableNode(): AccessibilityNodeInfo? {
        val root = rootInActiveWindow ?: return null
        val stack = ArrayDeque<AccessibilityNodeInfo>()
        stack.addLast(root)
        while (stack.isNotEmpty()) {
            val current = stack.removeLast()
            if (current.isFocused && current.isEditable) return current
            for (i in 0 until current.childCount) {
                current.getChild(i)?.let { stack.addLast(it) }
            }
        }
        return null
    }

    private fun placeCursorAfterInsertedText(node: AccessibilityNodeInfo, position: Int) {
        val selectionArgs = Bundle().apply {
            putInt(AccessibilityNodeInfo.ACTION_ARGUMENT_SELECTION_START_INT, position)
            putInt(AccessibilityNodeInfo.ACTION_ARGUMENT_SELECTION_END_INT, position)
        }
        // Best-effort: some fields reset the cursor to the end on
        // ACTION_SET_TEXT regardless, and that's an acceptable fallback,
        // not worth failing the whole insertion over.
        node.performAction(AccessibilityNodeInfo.ACTION_SET_SELECTION, selectionArgs)
    }

    private fun pasteFallback(node: AccessibilityNodeInfo, text: String): Boolean {
        val clipboard = getSystemService(ClipboardManager::class.java) ?: return false
        val previousClip = clipboard.primaryClip
        clipboard.setPrimaryClip(ClipData.newPlainText("VoxScribe dictation", text))
        val pasted = node.performAction(AccessibilityNodeInfo.ACTION_PASTE)
        if (previousClip != null) {
            Handler(Looper.getMainLooper()).postDelayed({
                clipboard.setPrimaryClip(previousClip)
            }, CLIPBOARD_RESTORE_DELAY_MS)
        }
        return pasted
    }

    /**
     * AccessibilityNodeInfo#recycle() is deprecated (a no-op) from API 33
     * onward since node pooling was removed, but it's still real and
     * needed on this app's minSdk 26..32 range to return nodes to the
     * pool -- suppressed rather than left as a bare warning since calling
     * it is deliberate, not an oversight.
     */
    @Suppress("DEPRECATION")
    private fun AccessibilityNodeInfo?.recycleCompat() {
        this?.recycle()
    }

    companion object {
        private const val TAG = "VoxScribeAccessibility"
        private const val CLIPBOARD_RESTORE_DELAY_MS = 500L

        /**
         * There is exactly one enabled instance of this service at a time
         * (Android manages that), so a nullable static reference is the
         * standard, accepted pattern for other components to reach it --
         * null whenever the user hasn't enabled the accessibility service.
         */
        var instance: VoxScribeAccessibilityService? = null
            private set
    }
}
