package com.voxscribe.android

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import android.content.Context
import android.util.Log
import java.io.File
import java.nio.FloatBuffer
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.log10
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow
import kotlin.math.sin

/**
 * The main English model: IBM Granite Speech 5.0 470M TurboCTC (Apache 2.0),
 * exported to ONNX and shrunk to int8, about 536 MB. Downloaded once; it types
 * English, French, Spanish, German, Italian and Portuguese (see [SpeechEngine]). On the user's own accented clips it
 * made about half the word errors of Whisper Base (18.8% against 34.9%) and
 * fewer than Whisper Small (24.5%), and decodes an 8 second phrase in under half a second on a mid phone.
 */
object GraniteModel {
    const val BASE_URL = "https://github.com/ahmedhmam1994/voxscribe-ai-voice-dictation/releases/download/models-2"
    const val MODEL_FILE = "granite-model.int8.onnx"
    const val TOKENS_FILE = "granite-tokens.txt"

    private val files = ModelDownload(
        folder = "granite-5-470m",
        baseUrl = BASE_URL,
        files = listOf(
            ModelFile(TOKENS_FILE, 147_550L, "7b1fe2af9e4fe0473f1e6319ab98abb218836c6061f067da545a51a94e78a30c"),
            ModelFile(MODEL_FILE, 535_729_949L, "43cce2414b229a81ad29ef440d1362722b82b58014e374054f74ffd9a61aba18"),
        ),
        logName = "Download the main English model",
        feature = "granite_model",
    )

    fun dir(context: Context): File = files.dir(context)

    fun isInstalled(context: Context): Boolean = files.isInstalled(context)

    fun status(context: Context): Map<String, Any?> = files.status(context)

    fun cancel() = files.cancel()

    /** Downloads, then reloads the recognizer so English switches to this model right away. */
    fun download(context: Context) {
        val app = context.applicationContext
        files.download(app) { if (isInstalled(app)) Thread { SpeechEngine.reload(app) }.start() }
    }

    fun delete(context: Context) {
        files.delete(context)
        val app = context.applicationContext
        Thread { SpeechEngine.reload(app) }.start()
    }
}

/**
 * Runs Granite: log-mel features, the ONNX model, then CTC greedy decoding.
 * The front end is a line by line port of the model's own Python feature
 * extractor (checked against it to 0.00004 on real clips). Not thread safe:
 * [SpeechEngine] serialises calls.
 */
class GraniteEngine private constructor(
    private val session: OrtSession,
    private val pieces: Array<String>,
    private val special: BooleanArray,
) {
    fun transcribe(samples: FloatArray): String {
        if (samples.size < SAMPLE_RATE / 4) return ""
        // Long recordings (file imports) go in pieces, so the model's output never
        // needs gigabytes of memory. Pieces start on a quiet spot where there is one.
        val out = StringBuilder()
        var start = 0
        while (start < samples.size) {
            var end = min(samples.size, start + CHUNK)
            if (end < samples.size) end = quietestNear(samples, end)
            val text = latinOnly(decodeIds(run(features(samples.copyOfRange(start, end)))))
            if (text.isNotBlank()) {
                if (out.isNotEmpty()) out.append(' ')
                out.append(text.trim())
            }
            start = end
        }
        return out.toString()
    }

    fun release() = session.close()

    private fun run(feats: Array<FloatArray>): IntArray {
        val frames = feats.size
        val flat = FloatBuffer.allocate(frames * FEATURE_DIM)
        for (row in feats) flat.put(row)
        flat.rewind()
        val env = OrtEnvironment.getEnvironment()
        OnnxTensor.createTensor(env, flat, longArrayOf(1, frames.toLong(), FEATURE_DIM.toLong())).use { input ->
            session.run(mapOf(INPUT to input)).use { result ->
                val logits = result[0] as OnnxTensor
                val shape = logits.info.shape
                val steps = shape[1].toInt()
                val vocab = shape[2].toInt()
                val buf = logits.floatBuffer
                return IntArray(steps) { t ->
                    var best = 0
                    var bestValue = Float.NEGATIVE_INFINITY
                    val base = t * vocab
                    for (v in 0 until vocab) {
                        val x = buf.get(base + v)
                        if (x > bestValue) {
                            bestValue = x
                            best = v
                        }
                    }
                    best
                }
            }
        }
    }

    /** CTC: merge repeats, drop the blank (id 0) and special tokens, then join the word pieces. */
    private fun decodeIds(ids: IntArray): String {
        val bytes = java.io.ByteArrayOutputStream()
        var prev = -1
        for (id in ids) {
            if (id != prev && id != BLANK && id < pieces.size && !special[id]) {
                val p = pieces[id]
                if (p.length == 6 && p.startsWith("<0x") && p.endsWith(">")) {
                    bytes.write(p.substring(3, 5).toInt(16))
                } else {
                    bytes.write(p.replace('▁', ' ').toByteArray(Charsets.UTF_8))
                }
            }
            prev = id
        }
        return bytes.toString("UTF-8").trimStart(' ')
    }

    companion object {
        /**
         * Granite's vocabulary holds other scripts too, and on an unclear sound it
         * can put out one of their letters ("Sendデ", 21 Nov 2026). Every language
         * it types here is written in Latin letters, so letters of any other
         * script are dropped. Digits, punctuation and symbols stay.
         */
        fun latinOnly(text: String): String {
            if (text.all { it.code < 0x250 }) return text
            val out = StringBuilder()
            var i = 0
            while (i < text.length) {
                val cp = text.codePointAt(i)
                val keep = !Character.isLetter(cp) ||
                    Character.UnicodeScript.of(cp) == Character.UnicodeScript.LATIN
                if (keep) out.appendCodePoint(cp)
                i += Character.charCount(cp)
            }
            return out.toString().replace(Regex(" {2,}"), " ").trim()
        }

        private const val TAG = "GraniteEngine"
        private const val SAMPLE_RATE = 16_000
        private const val INPUT = "features"
        private const val BLANK = 0
        private const val N_FFT = 512
        private const val WIN = 400
        private const val HOP = 160
        private const val MELS = 80
        private const val FEATURE_DIM = 320
        private const val CHUNK = 30 * SAMPLE_RATE

        /** Throws when the files are damaged or the library cannot load them. */
        fun load(context: Context): GraniteEngine {
            val dir = GraniteModel.dir(context)
            val lines = File(dir, GraniteModel.TOKENS_FILE).readLines(Charsets.UTF_8)
            val pieces = Array(lines.size) { lines[it].substringBeforeLast('\t') }
            val special = BooleanArray(lines.size) { lines[it].endsWith("\t1") }
            val options = OrtSession.SessionOptions().apply {
                setIntraOpNumThreads(4)
                setOptimizationLevel(OrtSession.SessionOptions.OptLevel.ALL_OPT)
            }
            val session = OrtEnvironment.getEnvironment()
                .createSession(File(dir, GraniteModel.MODEL_FILE).path, options)
            Log.i(TAG, "Granite loaded, ${pieces.size} tokens.")
            return GraniteEngine(session, pieces, special)
        }

        // --- Front end: torchaudio MelSpectrogram (HTK mel, no norm, power 2, centred reflect padding),
        // log10 floored 8 below the clip's peak, scaled, plus deltas, two frames stacked. ---

        private val window = FloatArray(N_FFT).also { w ->
            val off = (N_FFT - WIN) / 2
            for (n in 0 until WIN) w[off + n] = (0.5 - 0.5 * cos(2 * PI * n / WIN)).toFloat()
        }

        private val melBank: Array<FloatArray> = run {
            val bins = N_FFT / 2 + 1
            fun hzToMel(f: Double) = 2595.0 * log10(1.0 + f / 700.0)
            fun melToHz(m: Double) = 700.0 * (10.0.pow(m / 2595.0) - 1.0)
            val lo = hzToMel(0.0)
            val hi = hzToMel(SAMPLE_RATE / 2.0)
            val pts = DoubleArray(MELS + 2) { melToHz(lo + (hi - lo) * it / (MELS + 1)) }
            Array(MELS) { m ->
                FloatArray(bins) { k ->
                    val f = (SAMPLE_RATE / 2.0) * k / (bins - 1)
                    val down = (f - pts[m]) / (pts[m + 1] - pts[m])
                    val up = (pts[m + 2] - f) / (pts[m + 2] - pts[m + 1])
                    max(0.0, min(down, up)).toFloat()
                }
            }
        }

        private val cosTable = DoubleArray(N_FFT / 2) { cos(2 * PI * it / N_FFT) }
        private val sinTable = DoubleArray(N_FFT / 2) { sin(2 * PI * it / N_FFT) }

        /** Rows of 320 values: [log-mel 80, delta 80] for frame 2t, then the same for frame 2t+1. */
        internal fun features(input: FloatArray): Array<FloatArray> {
            val melFrames = input.size / HOP
            val numFrames = 2 * ((melFrames + 1) / 2)
            val need = (numFrames - 1) * HOP + 1
            val x = if (input.size < need) input.copyOf(need) else input
            val pad = N_FFT / 2
            val n = x.size
            fun sample(i: Int): Float = when {
                i < 0 -> x[-i]
                i >= n -> x[2 * (n - 1) - i]
                else -> x[i]
            }
            val re = DoubleArray(N_FFT)
            val im = DoubleArray(N_FFT)
            val power = DoubleArray(N_FFT / 2 + 1)
            val logMel = Array(numFrames) { FloatArray(MELS) }
            var peak = Float.NEGATIVE_INFINITY
            for (t in 0 until numFrames) {
                val startIdx = t * HOP - pad
                for (i in 0 until N_FFT) {
                    re[i] = (sample(startIdx + i) * window[i]).toDouble()
                    im[i] = 0.0
                }
                fft(re, im)
                for (k in power.indices) power[k] = re[k] * re[k] + im[k] * im[k]
                for (m in 0 until MELS) {
                    val bank = melBank[m]
                    var s = 0.0
                    for (k in power.indices) s += bank[k] * power[k]
                    val v = log10(max(s, 1e-10)).toFloat()
                    logMel[t][m] = v
                    if (v > peak) peak = v
                }
            }
            val floor = peak - 8f
            for (row in logMel) for (m in 0 until MELS) row[m] = max(row[m], floor) / 4f + 1f
            return Array(numFrames / 2) { pair ->
                val out = FloatArray(FEATURE_DIM)
                for (half in 0..1) {
                    val t = pair * 2 + half
                    val prev = logMel[max(t - 1, 0)]
                    val next = logMel[min(t + 1, numFrames - 1)]
                    val base = half * 2 * MELS
                    for (m in 0 until MELS) {
                        out[base + m] = logMel[t][m]
                        out[base + MELS + m] = (next[m] - prev[m]) / 2f
                    }
                }
                out
            }
        }

        /** In-place radix-2 FFT of length [N_FFT]. */
        private fun fft(re: DoubleArray, im: DoubleArray) {
            val n = re.size
            var j = 0
            for (i in 1 until n) {
                var bit = n shr 1
                while (j and bit != 0) {
                    j = j xor bit
                    bit = bit shr 1
                }
                j = j xor bit
                if (i < j) {
                    var tmp = re[i]; re[i] = re[j]; re[j] = tmp
                    tmp = im[i]; im[i] = im[j]; im[j] = tmp
                }
            }
            var len = 2
            while (len <= n) {
                val step = n / len
                val half = len / 2
                var i = 0
                while (i < n) {
                    for (k in 0 until half) {
                        val c = cosTable[k * step]
                        val s = -sinTable[k * step]
                        val ur = re[i + k]
                        val ui = im[i + k]
                        val vr = re[i + k + half] * c - im[i + k + half] * s
                        val vi = re[i + k + half] * s + im[i + k + half] * c
                        re[i + k] = ur + vr
                        im[i + k] = ui + vi
                        re[i + k + half] = ur - vr
                        im[i + k + half] = ui - vi
                    }
                    i += len
                }
                len = len shl 1
            }
        }

        /** Where to cut a long recording near [target]: the quietest 100 ms in the 2 s before it. */
        private fun quietestNear(x: FloatArray, target: Int): Int {
            val win = SAMPLE_RATE / 10
            var best = target
            var bestEnergy = Double.MAX_VALUE
            var pos = max(win, target - 2 * SAMPLE_RATE)
            while (pos + win <= target) {
                var e = 0.0
                for (i in pos until pos + win) e += x[i] * x[i]
                if (e < bestEnergy) {
                    bestEnergy = e
                    best = pos + win / 2
                }
                pos += win / 2
            }
            return best
        }
    }
}
