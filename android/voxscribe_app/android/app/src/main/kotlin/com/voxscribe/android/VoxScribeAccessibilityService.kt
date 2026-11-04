package com.voxscribe.android

import android.accessibilityservice.AccessibilityService
import android.content.ClipData
import android.content.ClipboardManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import android.view.accessibility.AccessibilityWindowInfo
import android.widget.Toast

/**
 * Powers floating-bubble mode (see BubblePermissions.kt): works with whichever
 * keyboard is active. Once enabled, this service tracks which text field is
 * focused and inserts dictated text into it directly via
 * AccessibilityNodeInfo.
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

    // The last piece of dictation typed, so "scratch that" and "delete last
    // word" know what to take back. Cleared whenever focus moves, like
    // lastWrittenText, so an edit never touches text VoxScribe did not write.
    private var lastInsertedChunk: String? = null
    private val recentChunks = ArrayDeque<String>()

    // Learns your words (see LearnedWords): the box as VoxScribe left it, where
    // the dictation in it starts, and the box as the person last left it.
    private var learnNode: AccessibilityNodeInfo? = null
    private var learnBase: String? = null
    private var learnFrom = 0
    private var learnLatest: String? = null
    private val learnHandler = Handler(Looper.getMainLooper())
    private val learnCheck = Runnable { checkForFix() }

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
            AccessibilityEvent.TYPE_VIEW_TEXT_CHANGED -> {
                onTextChanged(event)
                return
            }

            AccessibilityEvent.TYPE_VIEW_FOCUSED -> {
                // Chrome focuses the same box again right after VoxScribe types into it,
                // and the system bars or the keyboard can take focus mid-fix: only another
                // box in the same app ends it (leaving the app is a window change).
                if (event.packageName == learnNode?.packageName && event.source != learnNode) {
                    stopLearning()
                }
                focusedNode.recycleCompat()
                focusedNode = event.source
                lastWrittenText = null
            }

            AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED -> {
                // The window/app changed -- the previously focused node is
                // almost certainly stale now. Drop it rather than risk
                // inserting into a field that's no longer visible.
                // A toast or a menu in the same app, or VoxScribe's own toast, does not
                // end a fix in progress.
                val other = event.packageName != learnNode?.packageName && event.packageName != packageName
                if (other) stopLearning()
                focusedNode.recycleCompat()
                focusedNode = null
                lastWrittenText = null
            }
        }
        refreshBubbleVisibility()
    }

    /**
     * Shows the floating bubble only while the user is editing a text box with
     * the keyboard open, and hides it otherwise.
     */
    fun refreshBubbleVisibility() {
        val bubble = BubbleService.instance ?: return
        // Null while windows are switching; keep the current state then.
        val root = rootInActiveWindow ?: return
        val focused = root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)
        val editing = focused != null &&
            FieldSafety.allowsDictation(focused.isEditable, focused.isPassword, focused.inputType)
        focused.recycleCompat()
        val allWindows = windows
        // If the phone does not report windows, fall back to focus alone.
        val keyboardOpen = allWindows.isEmpty() ||
            allWindows.any { it.type == AccessibilityWindowInfo.TYPE_INPUT_METHOD }
        bubble.setFieldFocused(editing && keyboardOpen)
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

        // Never type into a password field, whatever the caller thinks the target is.
        if (FieldSafety.isSensitive(node.isPassword, node.inputType)) {
            debugLog("insert refused: password field")
            return false
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
        // Compare with what the field really holds now: our remembered text is
        // only trusted while the field still starts with it (see DictationText).
        // Real writing already in the field (an email draft) is kept and the
        // dictation goes at the cursor; a 0,0 cursor is not trusted (see DictationText).
        val result = DictationText.insertion(
            current = node.text?.toString().orEmpty(),
            lastWritten = lastWrittenText,
            dictated = text,
            selStart = node.textSelectionStart,
            selEnd = node.textSelectionEnd,
        )
        val newText = result.text

        val setTextArgs = Bundle().apply {
            putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, newText)
        }
        if (node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, setTextArgs)) {
            lastWrittenText = newText
            lastInsertedChunk = text
            recentChunks.addLast(text)
            while (recentChunks.size > 10) recentChunks.removeFirst()
            focusedNode = node
            placeCursorAfterInsertedText(node, result.cursor)
            startLearning(node, newText, text)
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

    /** The package name of the app that has focus now, for per-app profiles. */
    fun focusedPackage(): String? =
        focusedNode?.packageName?.toString() ?: rootInActiveWindow?.packageName?.toString()

    /**
     * Takes back some of what VoxScribe typed last ("scratch that", "delete
     * last word", "delete last sentence").
     */
    fun applyEdit(edit: VoiceCommands.Edit): Boolean =
        rewriteLastDictation("edit") { spoken -> VoiceCommands.computeDeletion(spoken, edit).remaining }

    /** "capitalize that", "all caps", "lowercase that": changes the last dictation in place. */
    fun applyTransform(transform: VoiceCommands.Transform): Boolean =
        rewriteLastDictation("transform") { spoken -> VoiceCommands.applyTransform(spoken, transform) }

    /** "replace X with Y": swaps a word in the last dictation. False when X is not in it. */
    fun applyReplace(from: String, to: String): Boolean =
        rewriteLastDictation("replace") { spoken -> VoiceCommands.applyReplace(spoken, from, to) }

    /**
     * "send it": taps the app's Send button. Most chat apps treat Enter as a new line, so the
     * button is looked for first, and Enter is only the fallback when the window has none.
     * "press enter" presses Enter itself. It reads button labels and ids only, never message
     * text, and it never acts on a password field.
     */
    fun sendMessage(kind: VoiceCommands.SendKind): Boolean {
        if (focusedFieldIsSensitive()) {
            debugLog("send refused: password field")
            return false
        }
        if (kind == VoiceCommands.SendKind.SEND) {
            val button = findSendButton()
            if (button != null) {
                val clicked = button.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                debugLog("send button clicked: $clicked")
                if (clicked) return true
            }
        }
        return pressEnter()
    }

    private fun findSendButton(): AccessibilityNodeInfo? {
        val root = rootInActiveWindow ?: return null
        val queue = ArrayDeque<AccessibilityNodeInfo>()
        queue.addLast(root)
        var visited = 0
        while (queue.isNotEmpty() && visited < MAX_NODES_SEARCHED) {
            val node = queue.removeFirst()
            visited++
            if (looksLikeSendButton(node)) return clickableSelfOrParent(node)
            for (i in 0 until node.childCount) node.getChild(i)?.let { queue.addLast(it) }
        }
        return null
    }

    private fun looksLikeSendButton(node: AccessibilityNodeInfo): Boolean {
        if (!node.isVisibleToUser || !node.isEnabled || node.isEditable) return false
        val label = node.contentDescription?.toString()?.trim().orEmpty()
        val id = node.viewIdResourceName.orEmpty().substringAfter('/').lowercase()
        return SEND_LABELS.any { label.equals(it, ignoreCase = true) } || id in SEND_IDS
    }

    private fun clickableSelfOrParent(node: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        var current: AccessibilityNodeInfo? = node
        repeat(3) {
            if (current?.isClickable == true) return current
            current = current?.parent
        }
        return null
    }

    /** The keyboard's Enter key, in the focused field. Needs Android 11. */
    fun pressEnter(): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) {
            debugLog("enter refused: needs Android 11 or newer")
            return false
        }
        var node = focusedNode
        if (node == null || !node.refresh() || !node.isEditable) {
            focusedNode = null
            node = findFocusedEditableNode()
        }
        if (node == null) {
            debugLog("enter refused: no focused text field")
            return false
        }
        if (FieldSafety.isSensitive(node.isPassword, node.inputType)) {
            debugLog("enter refused: password field")
            return false
        }
        val performed = node.performAction(AccessibilityNodeInfo.AccessibilityAction.ACTION_IME_ENTER.id)
        debugLog("enter performed: $performed")
        return performed
    }

    /**
     * Rewrites the last thing VoxScribe typed. Refuses when the field no longer
     * ends with that text, as the Windows app refuses when the window changed:
     * changing text the user never dictated would be worse than doing nothing.
     * [rewrite] gets the dictated words and returns their replacement (empty to
     * delete them), or null when the command does not apply.
     */
    private fun rewriteLastDictation(label: String, rewrite: (String) -> String?): Boolean {
        if (recentChunks.isEmpty()) {
            debugLog("$label refused: nothing was typed by VoxScribe yet")
            return false
        }
        var node = focusedNode
        if (node == null || !node.refresh() || !node.isEditable) {
            focusedNode = null
            node = findFocusedEditableNode()
            if (node == null) {
                debugLog("$label refused: no focused text field")
                return false
            }
        }
        node.refresh()
        if (FieldSafety.isSensitive(node.isPassword, node.inputType)) {
            debugLog("$label refused: password field")
            return false
        }
        val current = node.text?.toString().orEmpty()

        // Find the newest dictation still at the end of the field. Some apps trim
        // or change the trailing space, and the user may have deleted the latest
        // chunk by hand, so older ones are tried too.
        var chunk = ""
        var spoken = ""
        var at = -1
        for (candidate in recentChunks.reversed()) {
            val words = candidate.trimEnd()
            val found = current.lastIndexOf(words)
            if (words.isNotEmpty() && found >= 0 && current.substring(found + words.length).isBlank()) {
                chunk = candidate
                spoken = words
                at = found
                break
            }
        }
        if (at < 0) {
            debugLog("$label refused: the field no longer ends with any recent dictation (field has ${current.length} chars)")
            return false
        }
        val rewritten = rewrite(spoken)
        if (rewritten == null) {
            debugLog("$label refused: it does not apply to the last dictation")
            return false
        }
        // Keep the trailing space VoxScribe adds, so the next dictation does not run on.
        val trailing = chunk.substring(spoken.length)
        val kept = if (rewritten.isEmpty()) "" else rewritten + trailing
        val newText = current.substring(0, at) + kept

        val args = Bundle().apply {
            putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, newText)
        }
        if (!node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)) {
            debugLog("$label refused: the field would not accept the new text")
            return false
        }
        lastWrittenText = newText
        // A spoken edit is VoxScribe's own change, not a fix to learn from.
        if (learnBase != null) {
            learnBase = newText
            learnLatest = newText
        }
        lastInsertedChunk = kept.ifEmpty { null }
        recentChunks.remove(chunk)
        if (kept.isNotEmpty()) recentChunks.addLast(kept)
        focusedNode = node
        placeCursorAfterInsertedText(node, newText.length)
        debugLog("$label applied: ${current.length} to ${newText.length} chars")
        return true
    }

    /**
     * The text boxes on screen for [FormFill], in screen order, with the label
     * each one shows: its hint, the label tied to it, its description, the
     * text just before it, or its view id. Password boxes are left out.
     */
    fun formFields(): List<Pair<FormFill.Field, AccessibilityNodeInfo>> {
        val root = rootInActiveWindow ?: return emptyList()
        val found = mutableListOf<Pair<FormFill.Field, AccessibilityNodeInfo>>()
        // Text drawn just before a box is usually its label ("Phone" above the phone box).
        var lastText: String? = null
        val stack = ArrayDeque<AccessibilityNodeInfo>()
        stack.addLast(root)
        var visited = 0
        while (stack.isNotEmpty() && visited < MAX_NODES_SEARCHED && found.size < MAX_FORM_FIELDS) {
            val node = stack.removeLast()
            visited++
            // Visibility is not checked for boxes: Google Contacts wraps each name box in a
            // holder that reports itself hidden, and the keyboard hides the boxes under it.
            // A box only fills when its label was said, so a hidden one is never a surprise.
            val visible = node.isVisibleToUser
            if (node.isEditable) {
                if (node.isEnabled && FieldSafety.allowsDictation(true, node.isPassword, node.inputType)) {
                    val label = fieldLabel(node, lastText)
                    found += FormFill.Field(found.size, label, node.inputType) to node
                }
                lastText = null
                continue
            }
            if (visible) {
                node.text?.toString()?.trim()?.takeIf { it.isNotEmpty() && it.length <= MAX_LABEL_LENGTH }?.let { lastText = it }
            }
            for (i in node.childCount - 1 downTo 0) node.getChild(i)?.let { stack.addLast(it) }
        }
        return found
    }

    /** Watches [node] after a dictation, so a fix the person makes to it can be learned. */
    private fun startLearning(node: AccessibilityNodeInfo, newText: String, dictated: String) {
        val base = learnBase
        // A second dictation into the same box keeps the start of the first.
        if (base == null || learnNode != node || !newText.startsWith(base)) {
            learnFrom = (newText.length - dictated.length).coerceAtLeast(0)
        }
        learnNode = node
        learnBase = newText
        learnLatest = newText
        learnHandler.removeCallbacks(learnCheck)
    }

    private fun stopLearning(check: Boolean = true) {
        if (check) checkForFix()
        learnHandler.removeCallbacks(learnCheck)
        learnNode = null
        learnBase = null
        learnLatest = null
    }

    private fun onTextChanged(event: AccessibilityEvent) {
        val node = learnNode ?: return
        if (event.source?.let { it != node } == true) return
        // The event carries the new text; Chrome can still report the old text when asked.
        val now = if (event.text.isNotEmpty()) {
            event.text.joinToString("")
        } else if (node.refresh()) {
            node.text?.toString().orEmpty()
        } else {
            ""
        }
        if (now.isBlank()) {
            // Sent or cleared: learn from the box as it was just before.
            stopLearning()
            return
        }
        learnLatest = now
        learnHandler.removeCallbacks(learnCheck)
        learnHandler.postDelayed(learnCheck, LEARN_SETTLE_MS)
    }

    /** Learns the fix the person made since VoxScribe typed, if it is a clear spelling fix. */
    private fun checkForFix() {
        learnHandler.removeCallbacks(learnCheck)
        val base = learnBase ?: return
        val now = learnLatest ?: return
        if (now == base || !TextToolsStore.snapshot(this).learnFixes) return
        val fix = LearnedWords.fix(base, now, learnFrom, ScreenWords.common(this))
        fix ?: return
        learnBase = now
        val learned = LearnedWords.remember(this, fix) ?: return
        FirstRun.feature(this, "learned_word")
        debugLog("learned a fix")
        Toast.makeText(this, getString(R.string.learned_fix, learned.heard, learned.fixed), Toast.LENGTH_LONG).show()
    }

    /**
     * The text shown by the app being dictated into, for [ScreenWords]: what
     * its views say, including the box being typed in. Password boxes, the
     * keyboard and VoxScribe's own windows are skipped, and nothing is kept.
     */
    fun screenTexts(): List<String> {
        val roots = windows.filter { it.type == AccessibilityWindowInfo.TYPE_APPLICATION }
            .mapNotNull { it.root }
            .ifEmpty { listOfNotNull(rootInActiveWindow) }
            .filter { it.packageName?.toString() != packageName }
        val texts = mutableListOf<String>()
        var chars = 0
        var visited = 0
        val stack = ArrayDeque(roots)
        while (stack.isNotEmpty() && visited < MAX_NODES_SEARCHED && chars < MAX_SCREEN_CHARS) {
            val node = stack.removeLast()
            visited++
            if (node.isPassword) continue
            for (text in listOfNotNull(node.text, node.contentDescription)) {
                val value = text.toString().trim()
                if (value.isEmpty()) continue
                texts += value
                chars += value.length
            }
            for (i in node.childCount - 1 downTo 0) node.getChild(i)?.let { stack.addLast(it) }
        }
        return texts
    }

    private fun fieldLabel(node: AccessibilityNodeInfo, textBefore: String?): String {
        val candidates = listOfNotNull(
            node.hintText?.toString(),
            node.labeledBy?.text?.toString(),
            node.text?.toString()?.takeIf { node.isShowingHintText },
            node.contentDescription?.toString(),
            // Some apps (Google Contacts) draw the label inside the box itself.
            innerLabel(node),
            textBefore,
            FormFill.labelFromViewId(node.viewIdResourceName),
        )
        return candidates.firstOrNull { FormFill.aliases(it).isNotEmpty() }.orEmpty()
    }

    /** The first short label-like text drawn inside [box] that is not what the box holds, or null. */
    private fun innerLabel(box: AccessibilityNodeInfo): String? {
        val value = box.text?.toString()?.trim()
        val queue = ArrayDeque<AccessibilityNodeInfo>()
        for (i in 0 until box.childCount) box.getChild(i)?.let { queue.addLast(it) }
        var visited = 0
        while (queue.isNotEmpty() && visited < MAX_INNER_NODES) {
            val node = queue.removeFirst()
            visited++
            val text = node.text?.toString()?.trim()
            // Skips a country flag before "Phone (Mobile)".
            if (!text.isNullOrEmpty() && text != value && text.length <= MAX_LABEL_LENGTH &&
                FormFill.aliases(text).isNotEmpty()
            ) {
                return text
            }
            for (i in 0 until node.childCount) node.getChild(i)?.let { queue.addLast(it) }
        }
        return null
    }

    /** Types each of [fills] into its box from [fields]. Returns how many boxes took their text. */
    fun fillForm(fields: List<Pair<FormFill.Field, AccessibilityNodeInfo>>, fills: List<FormFill.Fill>): Int {
        stopLearning(check = false)
        var filled = 0
        for (fill in fills) {
            val node = fields.getOrNull(fill.index)?.second ?: continue
            if (!node.refresh() || FieldSafety.isSensitive(node.isPassword, node.inputType)) continue
            val args = Bundle().apply {
                putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, fill.value)
            }
            if (node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)) {
                filled++
                // A later dictation into the focused box adds to what is there instead of replacing it.
                if (node == focusedNode) lastWrittenText = fill.value
            }
        }
        debugLog("form fill: $filled of ${fills.size} boxes")
        return filled
    }

    /** True while a keyboard is on screen. */
    fun keyboardShown(): Boolean =
        windows.any { it.type == android.view.accessibility.AccessibilityWindowInfo.TYPE_INPUT_METHOD }

    /** Keeps the keyboard down while [hidden], then lets apps show it again. */
    fun hideKeyboard(hidden: Boolean) {
        softKeyboardController.showMode =
            if (hidden) SHOW_MODE_HIDDEN else SHOW_MODE_AUTO
    }

    /** True when the focused field is a password field, so nothing dictated may go near it. */
    fun focusedFieldIsSensitive(): Boolean {
        val root = rootInActiveWindow ?: return false
        val focused = root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT) ?: return false
        val sensitive = FieldSafety.isSensitive(focused.isPassword, focused.inputType)
        focused.recycleCompat()
        return sensitive
    }

    /** The focused box's android.text.InputType, or 0 when there is none. */
    fun focusedInputType(): Int {
        val root = rootInActiveWindow ?: return 0
        val focused = root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT) ?: return 0
        val type = focused.inputType
        focused.recycleCompat()
        return type
    }

    /** Debug builds only, so a refused undo can be told apart from a bug. */
    private fun debugLog(message: String) {
        if (applicationInfo.flags and android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE != 0) {
            Log.d("VoxPipeline", message)
        }
    }

    /** Depth-first search of the active window for a focused, editable node. */
    private fun findFocusedEditableNode(): AccessibilityNodeInfo? {
        val root = rootInActiveWindow ?: return null
        val stack = ArrayDeque<AccessibilityNodeInfo>()
        stack.addLast(root)
        while (stack.isNotEmpty()) {
            val current = stack.removeLast()
            if (current.isFocused &&
                FieldSafety.allowsDictation(current.isEditable, current.isPassword, current.inputType)
            ) {
                return current
            }
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
        if (pasted) {
            // The pasted text lands a moment later; watch the box from then.
            learnHandler.postDelayed({
                val now = if (node.refresh()) node.text?.toString().orEmpty() else ""
                if (now.endsWith(text.trimEnd())) startLearning(node, now, text)
            }, PASTE_SETTLE_MS)
        }
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
        private const val MAX_NODES_SEARCHED = 2500
        private const val MAX_FORM_FIELDS = 30
        private const val MAX_LABEL_LENGTH = 40
        private const val MAX_INNER_NODES = 20
        private const val MAX_SCREEN_CHARS = 20_000
        // How long the box must stay unchanged before a fix counts, so a word half typed is not learned.
        private const val LEARN_SETTLE_MS = 3_000L
        private const val PASTE_SETTLE_MS = 300L
        private val SEND_LABELS = listOf("send", "send message")
        private val SEND_IDS = setOf("send", "send_button", "btn_send", "send_btn", "button_send")

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
