package com.voxscribe.android

import android.annotation.SuppressLint
import android.app.PendingIntent
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.os.Build
import android.service.quicksettings.Tile
import android.service.quicksettings.TileService
import android.util.Log
import androidx.core.content.ContextCompat

/**
 * A Quick Settings tile that turns the floating button on and off, so it can
 * be brought back from the notification shade without opening the app.
 */
class DictationTileService : TileService() {

    override fun onStartListening() {
        super.onStartListening()
        refresh()
    }

    override fun onClick() {
        super.onClick()
        if (BubbleService.isRunning) {
            stopService(Intent(this, BubbleService::class.java))
            refresh(running = false)
            return
        }
        if (!BubblePermissions.hasOverlayPermission(this) || !BubblePermissions.isAccessibilityServiceEnabled(this)) {
            openActivity(TileLaunchActivity::class.java)
            return
        }
        // Start the button straight from here. Some phones (MIUI) silently block a
        // tile from opening even an invisible screen, so that is only the fallback.
        val started = runCatching {
            ContextCompat.startForegroundService(this, Intent(this, BubbleService::class.java))
        }.onFailure { Log.w(TAG, "Direct start refused, opening the launch screen", it) }.isSuccess
        Log.i(TAG, "Tile tapped, direct start ${if (started) "sent" else "refused"}")
        if (started) refresh(running = true) else openActivity(TileLaunchActivity::class.java)
    }

    // The Intent form is only used below Android 14, where it is the only one.
    @SuppressLint("StartActivityAndCollapseDeprecated")
    private fun openActivity(activity: Class<*>) {
        val intent = Intent(this, activity).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startActivityAndCollapse(
                PendingIntent.getActivity(this, 0, intent, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT),
            )
        } else {
            @Suppress("DEPRECATION")
            startActivityAndCollapse(intent)
        }
    }

    private fun refresh(running: Boolean = BubbleService.isRunning) {
        val tile = qsTile ?: return
        tile.state = if (running) Tile.STATE_ACTIVE else Tile.STATE_INACTIVE
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            tile.subtitle = getString(if (running) R.string.tile_on else R.string.tile_off)
        }
        tile.updateTile()
    }

    companion object {
        private const val TAG = "VoxTile"

        /** Asks the system to redraw the tile, after the button starts or stops. */
        fun requestRefresh(context: Context) {
            runCatching {
                requestListeningState(context, ComponentName(context, DictationTileService::class.java))
            }
        }
    }
}
