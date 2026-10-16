package com.voxscribe.android

import android.content.Context
import kotlin.math.max

/**
 * Where the floating button sits and when it hides. Plain maths, so it can be
 * tested without a phone.
 */
object BubblePlacement {

    data class Point(val x: Int, val y: Int)

    /** Fraction of the screen height, from the top, below which a release means "hide for a while". */
    const val SNOOZE_ZONE_START = 0.88f
    const val SNOOZE_MS = 10 * 60 * 1000L

    /** Gap kept from the side of the screen, in dp, wide enough to clear the system back gesture. */
    const val EDGE_INSET_DP = 32

    /** Keeps the whole button on the screen. */
    fun clamp(x: Int, y: Int, screenW: Int, screenH: Int, viewW: Int, viewH: Int): Point =
        Point(
            x.coerceIn(0, max(0, screenW - viewW)),
            y.coerceIn(0, max(0, screenH - viewH)),
        )

    /**
     * The nearer of the two sides, so the button rests beside one instead of floating mid-screen.
     * [inset] keeps it off the very edge, where Android's back gesture would catch a touch
     * meant for the button.
     */
    fun snapToEdge(x: Int, screenW: Int, viewW: Int, inset: Int = 0): Int {
        val left = inset.coerceAtLeast(0)
        val right = max(left, screenW - viewW - inset.coerceAtLeast(0))
        return if (x + viewW / 2 < screenW / 2) left else right
    }

    /** Letting go of a drag in the bottom strip hides the button for [SNOOZE_MS]. */
    fun shouldSnooze(releaseY: Float, screenH: Int): Boolean =
        screenH > 0 && releaseY >= screenH * SNOOZE_ZONE_START
}

/** Remembers where the user left the button. */
object BubblePositionStore {
    private const val PREFS = "voxscribe_bubble"
    private const val KEY_X = "x"
    private const val KEY_Y = "y"

    fun load(context: Context): BubblePlacement.Point? {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (!prefs.contains(KEY_X) || !prefs.contains(KEY_Y)) return null
        return BubblePlacement.Point(prefs.getInt(KEY_X, 0), prefs.getInt(KEY_Y, 0))
    }

    fun save(context: Context, x: Int, y: Int) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putInt(KEY_X, x).putInt(KEY_Y, y).apply()
    }
}
