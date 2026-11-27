package com.voxscribe.android

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.job.JobInfo
import android.app.job.JobParameters
import android.app.job.JobScheduler
import android.app.job.JobService
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.os.Handler
import android.os.Looper
import androidx.core.app.NotificationCompat

/**
 * Checks about every 15 minutes, while the user wants the floating button on,
 * that it still is. When the phone closed VoxScribe, Android also leaves its
 * accessibility service disconnected until the user switches it off and on,
 * and nothing on screen says so: this job notices and posts one notification
 * that opens the reconnect step. If only the button stopped, it starts it again.
 */
class BubbleWatchJob : JobService() {

    private val main = Handler(Looper.getMainLooper())

    override fun onStartJob(params: JobParameters?): Boolean {
        // The job may have just started the app; give Android a moment to
        // reconnect the accessibility service if it is going to.
        main.postDelayed({
            check(applicationContext)
            jobFinished(params, false)
        }, SETTLE_MS)
        return true
    }

    override fun onStopJob(params: JobParameters?): Boolean {
        main.removeCallbacksAndMessages(null)
        return true
    }

    companion object {
        private const val JOB_ID = 4201
        private const val NOTIFICATION_ID = 3
        private const val CHANNEL_ID = "voxscribe_alert"
        private const val SETTLE_MS = 4_000L
        private const val PERIOD_MS = 15 * 60_000L

        /** What the check should do, given the phone's state. */
        enum class Action { STOP_WATCHING, NOTHING, REVIVE, NOTIFY }

        fun decide(
            wanted: Boolean,
            running: Boolean,
            accessibilityOn: Boolean,
            accessibilityConnected: Boolean,
            alreadyNotified: Boolean,
        ): Action = when {
            !wanted -> Action.STOP_WATCHING
            running -> Action.NOTHING
            // Switched off by the user in Settings: their choice, not a break.
            !accessibilityOn -> Action.STOP_WATCHING
            accessibilityConnected -> Action.REVIVE
            alreadyNotified -> Action.NOTHING
            else -> Action.NOTIFY
        }

        /** Starts watching; called each time the floating button starts. */
        fun schedule(context: Context) {
            val scheduler = context.getSystemService(JobScheduler::class.java) ?: return
            val job = JobInfo.Builder(JOB_ID, ComponentName(context, BubbleWatchJob::class.java))
                .setPeriodic(PERIOD_MS)
                .build()
            runCatching { scheduler.schedule(job) }
        }

        fun cancel(context: Context) {
            context.getSystemService(JobScheduler::class.java)?.cancel(JOB_ID)
        }

        /** The button is back: drop the notification and allow a new one next time. */
        fun clearNotice(context: Context) {
            SettingsStore.setBrokenNotified(context, false)
            context.getSystemService(NotificationManager::class.java)?.cancel(NOTIFICATION_ID)
        }

        fun check(context: Context) {
            val app = context.applicationContext
            val action = decide(
                wanted = SettingsStore.bubbleWanted(app),
                running = BubbleService.isRunning,
                accessibilityOn = BubblePermissions.isAccessibilityServiceEnabled(app),
                accessibilityConnected = VoxScribeAccessibilityService.instance != null,
                alreadyNotified = SettingsStore.brokenNotified(app),
            )
            when (action) {
                Action.STOP_WATCHING -> cancel(app)
                Action.NOTHING -> Unit
                Action.REVIVE -> BubbleRevive.ifWanted(app)
                Action.NOTIFY -> {
                    SettingsStore.setBrokenNotified(app, true)
                    FirstRun.step(app, "bubble_broken")
                    notifyBroken(app)
                }
            }
        }

        private fun notifyBroken(app: Context) {
            val manager = app.getSystemService(NotificationManager::class.java) ?: return
            manager.createNotificationChannel(
                NotificationChannel(CHANNEL_ID, app.getString(R.string.alert_channel_name), NotificationManager.IMPORTANCE_HIGH),
            )
            val open = PendingIntent.getActivity(
                app,
                3,
                Intent(app, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                PendingIntent.FLAG_IMMUTABLE,
            )
            val text = app.getString(R.string.broken_text)
            runCatching {
                manager.notify(
                    NOTIFICATION_ID,
                    NotificationCompat.Builder(app, CHANNEL_ID)
                        .setSmallIcon(R.drawable.ic_mic)
                        .setContentTitle(app.getString(R.string.broken_title))
                        .setContentText(text)
                        .setStyle(NotificationCompat.BigTextStyle().bigText(text))
                        .setPriority(NotificationCompat.PRIORITY_HIGH)
                        .setAutoCancel(true)
                        .setContentIntent(open)
                        .build(),
                )
            }
        }
    }
}
