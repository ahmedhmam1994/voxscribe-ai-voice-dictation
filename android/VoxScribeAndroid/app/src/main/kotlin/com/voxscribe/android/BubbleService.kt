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
 * Recording/transcription runs through [DictationEngine] -- the same
 * shared pipeline VoxScribeInputMethodService.kt (keyboard mode) uses --
 * and inserts the result via [VoxScribeAccessibilityService.insertText].
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

    override fun onCreate() {
        super.onCreate()
        isRunning = true
        createNotificationChannel()
        addBubbleToWindow()
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
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        super.onDestroy()
        isRunning = false
        dictationEngine?.destroy()
        dictationEngine = null
        bubbleView?.let { view -> runCatching { windowManager?.removeView(view) } }
        bubbleView = null
    }

    // -- overlay window ---------------------------------------------------

    private fun addBubbleToWindow() {
        val wm = getSystemService(Context.WINDOW_SERVICE) as WindowManager
        windowManager = wm

        // Same theme-inheritance gotcha already hit and fixed for the IME
        // (see VoxScribeInputMethodService.kt's ContextThemeWrapper use): a
        // bare Service has no attached theme, so backgroundTint/colorOnPrimary
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
        params.x = 0
        params.y = 300
        layoutParams = params

        setState(BubbleState.IDLE)
        view.setOnTouchListener(BubbleTouchListener())
        wm.addView(view, params)
    }

    // -- drag vs. hold-to-talk ---------------------------------------------

    /**
     * Distinguishes a drag (reposition the bubble) from a hold-to-talk
     * gesture (record) using the same signal Android's own view system
     * uses for click-vs-drag: total movement since ACTION_DOWN against
     * ViewConfiguration's touch slop. Recording starts optimistically on
     * ACTION_DOWN -- matching the "hold" part of hold-to-talk -- and is
     * cancelled if the touch turns into a real drag, rather than waiting
     * for ACTION_UP to decide which gesture it was.
     */
    private inner class BubbleTouchListener : View.OnTouchListener {
        private val touchSlop = ViewConfiguration.get(this@BubbleService).scaledTouchSlop
        private var downRawX = 0f
        private var downRawY = 0f
        private var downParamX = 0
        private var downParamY = 0
        private var dragging = false
        private var holdActive = false

        override fun onTouch(v: View, event: MotionEvent): Boolean {
            val params = layoutParams ?: return false
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    downRawX = event.rawX
                    downRawY = event.rawY
                    downParamX = params.x
                    downParamY = params.y
                    dragging = false
                    holdActive = true
                    setState(BubbleState.RECORDING)
                    onHoldStart()
                }

                MotionEvent.ACTION_MOVE -> {
                    val dx = event.rawX - downRawX
                    val dy = event.rawY - downRawY
                    if (!dragging && (abs(dx) > touchSlop || abs(dy) > touchSlop)) {
                        dragging = true
                        if (holdActive) {
                            // Turned into a drag -- cancel the recording
                            // rather than let repositioning the bubble
                            // accidentally dictate ambient noise picked up
                            // mid-drag.
                            holdActive = false
                            onHoldCancel()
                            setState(BubbleState.IDLE)
                        }
                    }
                    if (dragging) {
                        params.x = downParamX + dx.toInt()
                        params.y = downParamY + dy.toInt()
                        windowManager?.updateViewLayout(v, params)
                    }
                }

                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    if (holdActive) {
                        holdActive = false
                        onHoldEnd()
                    }
                    dragging = false
                }
            }
            return true
        }
    }

    // -- state --------------------------------------------------------------

    private fun setState(newState: BubbleState) {
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
                view.imageTintList = ContextCompat.getColorStateList(this, R.color.vox_on_error)
                view.backgroundTintList = ContextCompat.getColorStateList(this, R.color.vox_error)
                view.contentDescription = getString(R.string.desc_bubble_recording)
            }

            BubbleState.TRANSCRIBING -> {
                view.setImageResource(R.drawable.ic_mic)
                view.imageTintList = ContextCompat.getColorStateList(this, R.color.vox_on_error)
                view.backgroundTintList = ContextCompat.getColorStateList(this, R.color.vox_transcribing)
                view.contentDescription = getString(R.string.desc_bubble_transcribing)
            }
        }
    }

    private fun hasRecordAudioPermission(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED

    private fun onHoldStart() {
        if (!hasRecordAudioPermission()) {
            // Phase 5's onboarding should prevent BubbleService from ever
            // starting without this already granted -- this is a defensive
            // fallback, not the primary path, mirroring the same check in
            // VoxScribeInputMethodService.kt.
            setState(BubbleState.IDLE)
            Toast.makeText(this, R.string.status_need_permission, Toast.LENGTH_SHORT).show()
            return
        }

        dictationEngine?.destroy()
        dictationEngine = DictationEngine(
            context = this,
            onResult = { text -> onDictationResult(text) },
            onFailure = { message ->
                setState(BubbleState.IDLE)
                Toast.makeText(this, message, Toast.LENGTH_SHORT).show()
            },
        ).also { it.startListening() }
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

    private fun onDictationResult(text: String) {
        setState(BubbleState.IDLE)
        if (text.isBlank()) return

        val inserted = VoxScribeAccessibilityService.instance?.insertText(text) ?: false
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

    private fun buildNotification(): Notification {
        val openApp = PendingIntent.getActivity(
            this,
            0,
            Intent(this, SetupActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE,
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_mic)
            .setContentTitle(getString(R.string.bubble_notification_title))
            .setContentText(getString(R.string.bubble_notification_text))
            .setOngoing(true)
            .setContentIntent(openApp)
            .build()
    }

    private enum class BubbleState { IDLE, RECORDING, TRANSCRIBING }

    companion object {
        private const val CHANNEL_ID = "voxscribe_bubble"
        private const val NOTIFICATION_ID = 1

        /**
         * There is exactly one instance of this service at a time (Android
         * manages that); lets SetupActivity's onboarding flow show whether
         * the bubble is currently active without needing a bound connection.
         */
        var isRunning: Boolean = false
            private set
    }
}
