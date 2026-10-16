package com.voxscribe.android

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.graphics.PixelFormat
import android.os.Build
import android.os.IBinder
import android.os.Looper
import android.os.Handler
import android.os.SystemClock
import android.util.Log
import android.view.ContextThemeWrapper
import android.view.Gravity
import android.view.LayoutInflater
import android.view.MotionEvent
import android.view.View
import android.view.ViewConfiguration
import android.view.WindowManager
import android.widget.Toast
import androidx.appcompat.widget.AppCompatImageView
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import kotlin.math.abs

/**
 * Hosts the floating dictation bubble: a WindowManager overlay window plus
 * the foreground service Android requires to keep it alive in the
 * background. See BubblePermissions.kt for the two permissions this
 * depends on (overlay + accessibility) -- checking those before starting
 * this service is the caller's job (Phase 5's onboarding UI), not this
 * class's.
 *
 * Recording/transcription runs through [DictationEngine] -- and inserts the
 * result via [VoxScribeAccessibilityService.insertText].
 * If that fails (accessibility service disabled, or no focused field was
 * ever tracked -- see that class's "known limitation" doc comment), the
 * dictated text is copied to the clipboard as a last resort so it's never
 * just silently lost, with a toast telling the user that's what happened.
 */
class BubbleService : Service() {

    private var windowManager: WindowManager? = null
    private var bubbleView: AppCompatImageView? = null
    private var layoutParams: WindowManager.LayoutParams? = null
    private var dictationEngine: DictationEngine? = null
    private var state = BubbleState.IDLE
    private var fieldFocused = false
    private var holdStartedAt = 0L
    private var lastInsertWorked = false
    private val gesture = HoldOrTap()
    private var snoozedUntil = 0L

    override fun onCreate() {
        super.onCreate()
        Telemetry.sendIfDue(this)
        isRunning = true
        instance = this
        createNotificationChannel()
        createAlertChannel()
        addBubbleToWindow()
        startAccessibilityWatch()
        // WhisperEngine.isAvailable() loads the ~160MB bundled model into
        // memory the first time it's called, which takes a few seconds --
        // doing that lazily on the first bubble press (as DictationEngine's
        // willUseWhisper getter would otherwise trigger, on the main thread,
        // during ACTION_DOWN) produced a visible freeze before recording
        // started. Warm it up here on a background thread instead, so it's
        // already loaded by the time the user actually holds the bubble.
        Thread { WhisperEngine.isAvailable(this) }.start()
    }

    @Suppress("InlinedApi") // constant only, ServiceCompat dispatches correctly per-OS-version
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // ServiceCompat picks the right startForeground() overload for the
        // running OS version on its own -- these type flags are only
        // actually required/enforced on Android 14+, but passing them
        // unconditionally is safe since they're just compile-time constants.
        // MICROPHONE is required alongside AndroidManifest.xml's
        // foregroundServiceType="...|microphone": without it, a background
        // service's AudioRecord silently captures nothing (confirmed via
        // logcat: "AppOps: Operation not started ... op=RECORD_AUDIO" /
        // "silencing record") even though the runtime permission is granted.
        ServiceCompat.startForeground(
            this,
            NOTIFICATION_ID,
            buildNotification(),
            ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE or ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE,
        )
        // The notification's "Show now" button brings a snoozed bubble back early.
        if (intent?.action == ACTION_UNSNOOZE) endSnooze()
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        super.onDestroy()
        isRunning = false
        instance = null
        watchHandler.removeCallbacksAndMessages(null)
        gesture.reset()
        getSystemService(NotificationManager::class.java)?.cancel(ALERT_NOTIFICATION_ID)
        dictationEngine?.destroy()
        dictationEngine = null
        bubbleView?.let { view -> runCatching { windowManager?.removeView(view) } }
        bubbleView = null
    }

    // -- overlay window ---------------------------------------------------

    private fun addBubbleToWindow() {
        val wm = getSystemService(Context.WINDOW_SERVICE) as WindowManager
        windowManager = wm

        // A bare Service has no attached theme, so backgroundTint/colorOnPrimary
        // etc. in bubble_view.xml would resolve to nothing without this.
        val themedContext = ContextThemeWrapper(this, R.style.Theme_VoxScribe)
        @Suppress("InflateParams") // correct here: this view IS the WindowManager root, no parent exists yet
        val view = LayoutInflater.from(themedContext)
            .inflate(R.layout.bubble_view, null) as AppCompatImageView
        bubbleView = view

        // TYPE_APPLICATION_OVERLAY unconditionally -- minSdk is 26 (O), the
        // same level that introduced it, so the older TYPE_PHONE fallback
        // some overlay-bubble examples still carry is dead code here.
        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
            PixelFormat.TRANSLUCENT,
        )
        params.gravity = Gravity.TOP or Gravity.START
        val saved = BubblePositionStore.load(this)
        params.x = saved?.x ?: 0
        params.y = saved?.y ?: 300
        layoutParams = params

        setState(BubbleState.IDLE)
        view.setOnTouchListener(BubbleTouchListener())
        wm.addView(view, params)
        view.post { keepOnScreen() }
        // Hidden until a text box is being edited; ask the typing service now.
        VoxScribeAccessibilityService.instance?.refreshBubbleVisibility()
    }

    // -- touch: hold to talk, tap to toggle, drag to move ---------------------

    /**
     * Holding the button records while the finger is down. A quick tap starts a
     * recording that carries on until the next tap (see [HoldOrTap]). Dragging
     * moves the button and cancels a recording that just started. Letting go
     * near a side edge snaps it there and remembers the spot, and letting go in
     * the bottom strip hides it for ten minutes.
     */
    private inner class BubbleTouchListener : View.OnTouchListener {
        // Twice Android's usual slop: a held finger drifts a little, and that must not
        // turn a press into a drag that moves the button instead of recording.
        private val touchSlop = ViewConfiguration.get(this@BubbleService).scaledTouchSlop * 2
        private var downRawX = 0f
        private var downRawY = 0f
        private var downParamX = 0
        private var downParamY = 0
        private var dragging = false

        override fun onTouch(v: View, event: MotionEvent): Boolean {
            val params = layoutParams ?: return false
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    downRawX = event.rawX
                    downRawY = event.rawY
                    downParamX = params.x
                    downParamY = params.y
                    dragging = false
                    perform(gesture.down(SystemClock.elapsedRealtime()))
                }

                MotionEvent.ACTION_MOVE -> {
                    val dx = event.rawX - downRawX
                    val dy = event.rawY - downRawY
                    if (!dragging && (abs(dx) > touchSlop || abs(dy) > touchSlop)) {
                        dragging = true
                        perform(gesture.dragged())
                    }
                    if (dragging) {
                        params.x = downParamX + dx.toInt()
                        params.y = downParamY + dy.toInt()
                        windowManager?.updateViewLayout(v, params)
                    }
                }

                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    perform(gesture.up(SystemClock.elapsedRealtime()))
                    if (dragging) finishDrag(v, params, event.rawY)
                    dragging = false
                }
            }
            return true
        }

        private fun finishDrag(v: View, params: WindowManager.LayoutParams, releaseY: Float) {
            val screen = resources.displayMetrics
            if (BubblePlacement.shouldSnooze(releaseY, screen.heightPixels)) {
                // Back where it was, so it returns to the same spot after the pause.
                params.x = downParamX
                params.y = downParamY
                windowManager?.updateViewLayout(v, params)
                snooze()
                return
            }
            val inset = (BubblePlacement.EDGE_INSET_DP * screen.density).toInt()
            params.x = BubblePlacement.snapToEdge(params.x, screen.widthPixels, v.width, inset)
            windowManager?.updateViewLayout(v, params)
            keepOnScreen()
            BubblePositionStore.save(this@BubbleService, params.x, params.y)
        }
    }

    /** Runs what [HoldOrTap] decided a touch means. */
    private fun perform(action: HoldOrTap.Action) {
        when (action) {
            HoldOrTap.Action.START -> {
                setState(BubbleState.RECORDING)
                if (onHoldStart()) {
                    watchHandler.removeCallbacks(recordingTimeout)
                    watchHandler.postDelayed(recordingTimeout, MAX_RECORDING_MS)
                } else {
                    gesture.reset()
                }
            }
            HoldOrTap.Action.STOP -> {
                watchHandler.removeCallbacks(recordingTimeout)
                onHoldEnd()
            }
            HoldOrTap.Action.CANCEL -> {
                watchHandler.removeCallbacks(recordingTimeout)
                onHoldCancel()
                setState(BubbleState.IDLE)
            }
            HoldOrTap.Action.NONE -> Unit
        }
    }

    // A tap-started recording that nobody stops would keep the microphone open.
    private val recordingTimeout = Runnable { perform(gesture.forceStop()) }

    private fun keepOnScreen() {
        val view = bubbleView ?: return
        val params = layoutParams ?: return
        val screen = resources.displayMetrics
        val p = BubblePlacement.clamp(params.x, params.y, screen.widthPixels, screen.heightPixels, view.width, view.height)
        if (p.x != params.x || p.y != params.y) {
            params.x = p.x
            params.y = p.y
            windowManager?.updateViewLayout(view, params)
        }
    }

    // -- snooze ---------------------------------------------------------------

    private fun isSnoozed(): Boolean = snoozedUntil > SystemClock.elapsedRealtime()

    private val unsnooze = Runnable { endSnooze() }

    private fun snooze() {
        snoozedUntil = SystemClock.elapsedRealtime() + BubblePlacement.SNOOZE_MS
        watchHandler.removeCallbacks(unsnooze)
        watchHandler.postDelayed(unsnooze, BubblePlacement.SNOOZE_MS)
        applyVisibility()
        refreshNotification()
        Toast.makeText(this, R.string.bubble_snoozed, Toast.LENGTH_LONG).show()
    }

    private fun endSnooze() {
        snoozedUntil = 0L
        watchHandler.removeCallbacks(unsnooze)
        applyVisibility()
        refreshNotification()
        VoxScribeAccessibilityService.instance?.refreshBubbleVisibility()
    }

    // -- state --------------------------------------------------------------

    /**
     * Called by the typing service: the bubble shows only while a text box is
     * being edited with the keyboard open.
     */
    fun setFieldFocused(focused: Boolean) {
        fieldFocused = focused
        applyVisibility()
    }

    private fun applyVisibility() {
        val view = bubbleView ?: return
        // Never hide it under the user's finger while recording or transcribing.
        val target = if ((fieldFocused && !isSnoozed()) || state != BubbleState.IDLE) View.VISIBLE else View.GONE
        if (view.visibility != target) view.visibility = target
    }

    private fun setState(newState: BubbleState) {
        state = newState
        val view = bubbleView ?: return
        when (newState) {
            BubbleState.IDLE -> {
                view.setImageResource(R.drawable.ic_mic)
                view.imageTintList = ContextCompat.getColorStateList(this, R.color.vox_on_primary)
                view.backgroundTintList = ContextCompat.getColorStateList(this, R.color.vox_primary)
                view.contentDescription = getString(R.string.desc_bubble_idle)
            }

            BubbleState.RECORDING -> {
                view.setImageResource(R.drawable.ic_stop)
                view.imageTintList = ContextCompat.getColorStateList(this, R.color.vox_on_primary)
                view.backgroundTintList = ContextCompat.getColorStateList(this, R.color.vox_primary_pressed)
                view.contentDescription = getString(R.string.desc_bubble_recording)
            }

            BubbleState.TRANSCRIBING -> {
                view.setImageResource(R.drawable.ic_mic)
                view.imageTintList = ContextCompat.getColorStateList(this, R.color.vox_on_primary)
                view.backgroundTintList = ContextCompat.getColorStateList(this, R.color.vox_transcribing)
                view.contentDescription = getString(R.string.desc_bubble_transcribing)
            }
        }
        applyVisibility()
    }

    private fun hasRecordAudioPermission(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED

    private fun onHoldStart(): Boolean {
        if (!hasRecordAudioPermission()) {
            // Phase 5's onboarding should prevent BubbleService from ever
            // starting without this already granted -- this is a defensive
            // fallback, not the primary path.
            setState(BubbleState.IDLE)
            Toast.makeText(this, R.string.status_need_permission, Toast.LENGTH_SHORT).show()
            return false
        }

        holdStartedAt = SystemClock.elapsedRealtime()
        dictationEngine?.destroy()
        dictationEngine = DictationEngine(
            context = this,
            onResult = { text -> onDictationResult(text) },
            onFailure = { message ->
                watchHandler.removeCallbacks(recordingTimeout)
                gesture.reset()
                setState(BubbleState.IDLE)
                Toast.makeText(this, message, Toast.LENGTH_SHORT).show()
            },
            interactive = true,
            focusedPackage = { VoxScribeAccessibilityService.instance?.focusedPackage() },
            onSpecial = { spoken -> onSpecialResult(spoken) },
            onSend = { kind -> sendAfterTyping(kind) },
        ).also { it.startListening() }
        return true
    }

    private fun onHoldEnd() {
        setState(BubbleState.TRANSCRIBING)
        dictationEngine?.stopListening()
    }

    private fun onHoldCancel() {
        dictationEngine?.cancel()
        dictationEngine?.destroy()
        dictationEngine = null
    }

    /** An editing command, a template prompt, or "send it": not text to type. */
    private fun onSpecialResult(spoken: Spoken) {
        setState(BubbleState.IDLE)
        val service = VoxScribeAccessibilityService.instance
        when (spoken) {
            is Spoken.Edit -> {
                val done = service?.applyEdit(spoken.edit) ?: false
                if (service == null) Log.d("VoxPipeline", "edit refused: accessibility service not connected")
                if (!done) Toast.makeText(this, R.string.edit_cant_undo, Toast.LENGTH_SHORT).show()
            }
            is Spoken.Transform -> {
                val done = service?.applyTransform(spoken.transform) ?: false
                if (!done) Toast.makeText(this, R.string.edit_cant_change, Toast.LENGTH_SHORT).show()
            }
            is Spoken.Replace -> {
                // "replace the battery with a new one" is ordinary speech unless
                // the last dictation really contains it, so type it as it was said.
                if (!(service?.applyReplace(spoken.from, spoken.to) ?: false)) typeAsDictation(spoken.raw)
            }
            is Spoken.Send -> performSend(spoken.kind)
            is Spoken.TemplatePrompt -> Toast.makeText(
                this,
                getString(R.string.template_prompt, spoken.name, spoken.slot),
                Toast.LENGTH_LONG,
            ).show()
            Spoken.TemplateCancelled -> Toast.makeText(this, R.string.template_cancelled, Toast.LENGTH_SHORT).show()
            is Spoken.Text -> Unit
        }
    }

    private fun performSend(kind: VoiceCommands.SendKind) {
        val done = VoxScribeAccessibilityService.instance?.sendMessage(kind) ?: false
        if (!done) Toast.makeText(this, R.string.send_cant_press, Toast.LENGTH_SHORT).show()
    }

    /** "how are you? send it": waits a moment for the text to land in the box, then sends. */
    private fun sendAfterTyping(kind: VoiceCommands.SendKind) {
        if (!lastInsertWorked) return
        watchHandler.postDelayed({ performSend(kind) }, SEND_DELAY_MS)
    }

    /** Runs the words through the pipeline again with "replace X with Y" switched off, and types the result. */
    private fun typeAsDictation(raw: String) {
        val options = TextPipeline.optionsFor(this, VoxScribeAccessibilityService.instance?.focusedPackage())
        when (val spoken = TextPipeline.process(raw, options, interactive = true, allowReplace = false)) {
            is Spoken.Text -> onDictationResult(spoken.text)
            else -> onSpecialResult(spoken)
        }
    }

    private fun onDictationResult(heard: String) {
        setState(BubbleState.IDLE)
        lastInsertWorked = false
        if (heard.isBlank()) return
        // An email, web address, number or phone box gets the text the way it expects.
        val inputType = VoxScribeAccessibilityService.instance?.focusedInputType() ?: 0
        val text = FieldShape.shape(heard, inputType)
        if (text.isBlank()) {
            Toast.makeText(this, R.string.bubble_field_no_match, Toast.LENGTH_SHORT).show()
            return
        }

        // A password field must never receive dictation, or see it in the history or on the clipboard.
        if (VoxScribeAccessibilityService.instance?.focusedFieldIsSensitive() == true) {
            Toast.makeText(this, R.string.bubble_password_blocked, Toast.LENGTH_SHORT).show()
            return
        }

        HistoryStore.add(
            this,
            HistoryEntry(
                text = text,
                atMillis = System.currentTimeMillis(),
                durationMillis = SystemClock.elapsedRealtime() - holdStartedAt,
            ),
        )
        // A trailing space keeps the next dictation in the same box from running into this one.
        val spaceAfter = SettingsStore.trailingSpaceEnabled(this) && !FieldShape.noTrailingSpace(inputType)
        val toInsert = if (spaceAfter) "$text " else text
        val inserted = VoxScribeAccessibilityService.instance?.insertText(toInsert) ?: false
        lastInsertWorked = inserted
        if (!inserted) {
            val clipboard = getSystemService(ClipboardManager::class.java)
            clipboard?.setPrimaryClip(ClipData.newPlainText("VoxScribe dictation", text))
            Toast.makeText(this, R.string.bubble_insert_failed_clipboard_fallback, Toast.LENGTH_SHORT).show()
        }
    }

    // -- notification ---------------------------------------------------------

    private fun createNotificationChannel() {
        // No SDK_INT guard needed -- NotificationChannel has existed since
        // API 26 (O), same as minSdk.
        val manager = getSystemService(NotificationManager::class.java)
        val channel = NotificationChannel(
            CHANNEL_ID,
            getString(R.string.bubble_notification_channel_name),
            NotificationManager.IMPORTANCE_MIN,
        ).apply {
            description = getString(R.string.bubble_notification_channel_desc)
        }
        manager.createNotificationChannel(channel)
    }

    // -- lost accessibility connection -----------------------------------------

    private val watchHandler = Handler(Looper.getMainLooper())
    private var disconnectedChecks = 0
    private var alertShowing = false

    private val watchAccessibility = object : Runnable {
        override fun run() {
            // After an app update Android can leave the accessibility service
            // switched on but disconnected (or flagged as crashed). Nothing
            // reaches the bubble then, so it silently never appears. Say so,
            // with a one tap way to fix it, instead of failing quietly.
            val connected = VoxScribeAccessibilityService.instance != null
            val enabled = BubblePermissions.isAccessibilityServiceEnabled(this@BubbleService)
            disconnectedChecks = if (enabled && !connected) disconnectedChecks + 1 else 0
            // Two checks in a row (about ten seconds), so a normal start up is not flagged.
            val shouldAlert = disconnectedChecks >= 2
            if (shouldAlert != alertShowing) {
                alertShowing = shouldAlert
                val manager = getSystemService(NotificationManager::class.java)
                if (shouldAlert) manager?.notify(ALERT_NOTIFICATION_ID, buildAlertNotification())
                else manager?.cancel(ALERT_NOTIFICATION_ID)
            }
            watchHandler.postDelayed(this, WATCH_INTERVAL_MS)
        }
    }

    private fun startAccessibilityWatch() {
        watchHandler.postDelayed(watchAccessibility, WATCH_INTERVAL_MS)
    }

    private fun createAlertChannel() {
        val channel = NotificationChannel(
            ALERT_CHANNEL_ID,
            getString(R.string.alert_channel_name),
            NotificationManager.IMPORTANCE_HIGH,
        )
        getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
    }

    private fun buildAlertNotification(): Notification {
        val openSettings = PendingIntent.getActivity(
            this,
            1,
            BubblePermissions.accessibilitySettingsIntent().addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
            PendingIntent.FLAG_IMMUTABLE,
        )
        return NotificationCompat.Builder(this, ALERT_CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_mic)
            .setContentTitle(getString(R.string.alert_title))
            .setContentText(getString(R.string.alert_text))
            .setStyle(NotificationCompat.BigTextStyle().bigText(getString(R.string.alert_text)))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(openSettings)
            .build()
    }

    private fun buildNotification(): Notification {
        val openApp = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE,
        )
        val snoozed = isSnoozed()
        val builder = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_mic)
            .setContentTitle(getString(R.string.bubble_notification_title))
            .setContentText(
                getString(if (snoozed) R.string.bubble_notification_snoozed else R.string.bubble_notification_text),
            )
            .setOngoing(true)
            .setContentIntent(openApp)
        if (snoozed) {
            val showNow = PendingIntent.getService(
                this,
                2,
                Intent(this, BubbleService::class.java).setAction(ACTION_UNSNOOZE),
                PendingIntent.FLAG_IMMUTABLE,
            )
            builder.addAction(R.drawable.ic_mic, getString(R.string.bubble_show_now), showNow)
        }
        return builder.build()
    }

    private fun refreshNotification() {
        getSystemService(NotificationManager::class.java)?.notify(NOTIFICATION_ID, buildNotification())
    }

    private enum class BubbleState { IDLE, RECORDING, TRANSCRIBING }

    companion object {
        private const val CHANNEL_ID = "voxscribe_bubble"
        private const val NOTIFICATION_ID = 1
        private const val ALERT_NOTIFICATION_ID = 2
        private const val ALERT_CHANNEL_ID = "voxscribe_alert"
        private const val WATCH_INTERVAL_MS = 5_000L
        private const val ACTION_UNSNOOZE = "com.voxscribe.android.UNSNOOZE"
        private const val MAX_RECORDING_MS = 120_000L
        private const val SEND_DELAY_MS = 350L

        /**
         * There is exactly one instance of this service at a time (Android
         * manages that); lets the app UI show whether
         * the bubble is currently active without needing a bound connection.
         */
        var isRunning: Boolean = false
            private set

        /** The running service, or null. Lets the typing service show and hide the bubble. */
        var instance: BubbleService? = null
            private set
    }
}
