package com.voxscribe.android

import android.animation.Animator
import android.animation.AnimatorListenerAdapter
import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.RectF
import android.os.SystemClock
import android.util.AttributeSet
import android.view.animation.DecelerateInterpolator
import androidx.appcompat.widget.AppCompatImageView
import androidx.core.content.ContextCompat
import kotlin.math.sin

/**
 * The floating button. Normally it just shows its icon; while recording it
 * draws a live mic level instead (five bars that ripple out from the center
 * as you talk), and while transcribing a slow wave through the same bars.
 * BubbleService picks the mode and feeds [pushLevel] from DictationEngine.
 * In the last seconds before a recording's time limit, a ring fills in
 * around the edge so the cut-off never comes as a surprise.
 *
 * Behind the bars, a soft disc swells with your voice; while transcribing an
 * arc runs around the edge. [ping] sends one ring out from the middle, so a
 * new user notices the button the first time it appears.
 *
 * The level is information, so it always moves; the transcribing wave, the
 * arc and the ping are decoration and stand still when the system's
 * animations are switched off (Developer options animator scale 0, or Remove
 * animations in Accessibility).
 */
class BubbleView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
) : AppCompatImageView(context, attrs) {

    enum class Mode { ICON, LEVEL, WORKING }

    var mode = Mode.ICON
        set(value) {
            if (field == value) return
            field = value
            if (value == Mode.LEVEL) {
                history.fill(0f)
                smoothed = 0f
                pending = 0f
            }
            if (value == Mode.ICON) removeCallbacks(frame) else postOnAnimation(frame)
            invalidate()
        }

    var barColor: Int
        get() = barPaint.color
        set(value) {
            barPaint.color = value
            invalidate()
        }

    /** When the recording will be stopped (elapsedRealtime), or 0 for no limit. */
    var recordingDeadline = 0L

    private val barPaint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val ringPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
    }
    private val glowPaint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val arcPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
    }
    private val pingPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE }
    private var pingAnimator: ValueAnimator? = null
    private var pingProgress = -1f
    private val ring = RectF()
    private val bar = RectF()
    // Newest level first. The center bar shows history[0]; the bars beside it
    // show older values, so a word "ripples" outward from the middle.
    private val history = FloatArray(5)
    private var smoothed = 0f
    private var pending = 0f
    private var phase = 0f

    /** A new 0 to 1 level from the microphone (main thread). */
    fun pushLevel(level: Float) {
        if (level > pending) pending = level
    }

    private val frame = object : Runnable {
        override fun run() {
            if (mode == Mode.ICON) return
            if (mode == Mode.LEVEL) {
                val target = pending
                pending = 0f
                smoothed = if (target > smoothed) {
                    smoothed + (target - smoothed) * 0.6f
                } else {
                    smoothed * 0.8f + target * 0.2f
                }
                System.arraycopy(history, 0, history, 1, history.size - 1)
                history[0] = smoothed
                invalidate()
            } else if (ValueAnimator.areAnimatorsEnabled()) {
                phase += 0.16f
                invalidate()
            }
            postOnAnimation(this)
        }
    }

    /** One ring that grows out from the middle and fades. Skipped when animations are off. */
    fun ping() {
        if (!ValueAnimator.areAnimatorsEnabled()) return
        pingAnimator?.cancel()
        pingAnimator = ValueAnimator.ofFloat(0f, 1f).apply {
            duration = PING_MS
            interpolator = DecelerateInterpolator(1.6f)
            addUpdateListener {
                pingProgress = it.animatedValue as Float
                invalidate()
            }
            addListener(object : AnimatorListenerAdapter() {
                override fun onAnimationEnd(animation: Animator) {
                    pingProgress = -1f
                    invalidate()
                }
            })
            start()
        }
    }

    override fun onDetachedFromWindow() {
        removeCallbacks(frame)
        pingAnimator?.cancel()
        super.onDetachedFromWindow()
    }

    override fun onDraw(canvas: Canvas) {
        val density = resources.displayMetrics.density
        if (mode == Mode.ICON) {
            super.onDraw(canvas)
            drawPing(canvas, density)
            return
        }
        if (mode == Mode.LEVEL) drawGlow(canvas)
        if (mode == Mode.WORKING) drawArc(canvas, density)
        val barWidth = 3.5f * density
        val gap = 2.5f * density
        val maxHeight = height * 0.46f
        val minHeight = barWidth
        val total = 5 * barWidth + 4 * gap
        var x = (width - total) / 2f
        val centerY = height / 2f
        for (i in 0 until 5) {
            val value = if (mode == Mode.LEVEL) {
                // 0,1,2,1,0 steps from the middle; outer bars a little lower.
                val distance = kotlin.math.abs(i - 2)
                history[distance * 2] * (1f - 0.18f * distance)
            } else {
                0.25f + 0.35f * (0.5f + 0.5f * sin(phase - i * 0.7f))
            }
            val h = minHeight + value.coerceIn(0f, 1f) * (maxHeight - minHeight)
            bar.set(x, centerY - h / 2f, x + barWidth, centerY + h / 2f)
            canvas.drawRoundRect(bar, barWidth / 2f, barWidth / 2f, barPaint)
            x += barWidth + gap
        }
        if (mode == Mode.LEVEL) drawLimitRing(canvas, density)
    }

    /** A disc in the bar color, faint and small in silence, larger as you speak. */
    private fun drawGlow(canvas: Canvas) {
        val radius = minOf(width, height) / 2f
        glowPaint.color = barPaint.color
        glowPaint.alpha = (22 + 34 * smoothed).toInt()
        canvas.drawCircle(width / 2f, height / 2f, radius * (0.5f + 0.38f * smoothed), glowPaint)
    }

    private fun drawArc(canvas: Canvas, density: Float) {
        if (!ValueAnimator.areAnimatorsEnabled()) return
        val stroke = 2.5f * density
        val inset = 3f * density + stroke / 2f
        arcPaint.strokeWidth = stroke
        arcPaint.color = barPaint.color
        arcPaint.alpha = 150
        ring.set(inset, inset, width - inset, height - inset)
        canvas.drawArc(ring, phase * 40f % 360f, 80f, false, arcPaint)
    }

    private fun drawPing(canvas: Canvas, density: Float) {
        if (pingProgress < 0f) return
        val radius = minOf(width, height) / 2f
        val stroke = 2.5f * density
        pingPaint.strokeWidth = stroke
        pingPaint.color = ContextCompat.getColor(context, R.color.vox_on_primary)
        pingPaint.alpha = (200 * (1f - pingProgress)).toInt()
        canvas.drawCircle(
            width / 2f,
            height / 2f,
            (radius - stroke) * (0.45f + 0.55f * pingProgress),
            pingPaint,
        )
    }

    private fun drawLimitRing(canvas: Canvas, density: Float) {
        if (recordingDeadline == 0L) return
        val remaining = recordingDeadline - SystemClock.elapsedRealtime()
        if (remaining >= LIMIT_WARNING_MS) return
        val filled = (1f - remaining.toFloat() / LIMIT_WARNING_MS).coerceIn(0f, 1f)
        val stroke = 2.5f * density
        val inset = 3f * density + stroke / 2f
        ringPaint.strokeWidth = stroke
        ringPaint.color = barPaint.color
        ring.set(inset, inset, width - inset, height - inset)
        canvas.drawArc(ring, -90f, 360f * filled, false, ringPaint)
    }

    companion object {
        /** How long before the time limit the ring starts filling. */
        const val LIMIT_WARNING_MS = 15_000L

        private const val PING_MS = 900L
    }
}
