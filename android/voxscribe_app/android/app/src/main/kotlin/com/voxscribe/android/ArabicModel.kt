package com.voxscribe.android

import android.content.Context
import android.util.Log
import com.k2fsa.sherpa.onnx.FeatureConfig
import com.k2fsa.sherpa.onnx.OnlineModelConfig
import com.k2fsa.sherpa.onnx.OnlineRecognizer
import com.k2fsa.sherpa.onnx.OnlineRecognizerConfig
import com.k2fsa.sherpa.onnx.OnlineTransducerModelConfig
import java.io.File

/**
 * The Arabic model: NVIDIA Nemotron 3.5 ASR Streaming 0.6B (OpenMDW 1.1), the
 * int8 export from sherpa-onnx, about 682 MB. Downloaded once; it types Arabic
 * and Turkish (see [SpeechEngine]). On the user's own Egyptian Arabic it was
 * near word for word, where Whisper Base could not follow at all, and it decodes a 7 second phrase in about a second on a mid phone.
 */
object ArabicModel {
    const val ENCODER = "nemotron-encoder.int8.onnx"
    const val DECODER = "nemotron-decoder.int8.onnx"
    const val JOINER = "nemotron-joiner.int8.onnx"
    const val TOKENS = "nemotron-tokens.txt"

    private val files = ModelDownload(
        folder = "nemotron-3.5-0.6b",
        baseUrl = GraniteModel.BASE_URL,
        files = listOf(
            ModelFile(TOKENS, 131_440L, "729cc103155bafa785f9cd45746cd41cabe97eab7182fc04d594129587958f8a"),
            ModelFile(DECODER, 14_978_075L, "19f9c98fc6d0a2c33a65a43b36fdb2e914c26c0aa9764be3aebc502a1e982fb0"),
            ModelFile(JOINER, 9_504_438L, "4101c7c679a0bc30483794b27a059e34e79232aa2068d78d51231a22c8b0d7ce"),
            ModelFile(ENCODER, 657_601_403L, "012e9321373af99021415e0b0eb3ec827b4be3153be6f30d9b448fe65e896e68"),
        ),
        logName = "Download the Arabic model",
        feature = "arabic_model",
    )

    fun dir(context: Context): File = files.dir(context)

    fun isInstalled(context: Context): Boolean = files.isInstalled(context)

    fun status(context: Context): Map<String, Any?> = files.status(context)

    fun cancel() = files.cancel()

    /** Downloads, then reloads the recognizer so Arabic switches to this model right away. */
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

/** Runs Nemotron on a whole recording. Not thread safe: [SpeechEngine] serialises calls. */
class ArabicEngine private constructor(
    private val recognizer: OnlineRecognizer,
    private val language: String,
) {

    fun transcribe(samples: FloatArray): String {
        val stream = recognizer.createStream("")
        try {
            stream.setOption("language", language)
            stream.acceptWaveform(samples, SAMPLE_RATE)
            // A second of silence flushes the last words out of the streaming model.
            stream.acceptWaveform(FloatArray(SAMPLE_RATE), SAMPLE_RATE)
            stream.inputFinished()
            while (recognizer.isReady(stream)) recognizer.decode(stream)
            return recognizer.getResult(stream).text.trim()
        } finally {
            stream.release()
        }
    }

    fun release() = recognizer.release()

    companion object {
        private const val TAG = "ArabicEngine"
        private const val SAMPLE_RATE = 16_000

        /** [language] is one of [SpeechEngine]'s Nemotron codes, such as "ar". Throws when the files are damaged or the library cannot load them. */
        fun load(context: Context, language: String): ArabicEngine {
            val dir = ArabicModel.dir(context)
            val config = OnlineRecognizerConfig(
                featConfig = FeatureConfig(sampleRate = SAMPLE_RATE, featureDim = 80),
                modelConfig = OnlineModelConfig(
                    transducer = OnlineTransducerModelConfig(
                        encoder = File(dir, ArabicModel.ENCODER).path,
                        decoder = File(dir, ArabicModel.DECODER).path,
                        joiner = File(dir, ArabicModel.JOINER).path,
                    ),
                    tokens = File(dir, ArabicModel.TOKENS).path,
                    numThreads = 2,
                    provider = "cpu",
                ),
                decodingMethod = "greedy_search",
            )
            return ArabicEngine(OnlineRecognizer(null, config), language)
                .also { Log.i(TAG, "Nemotron loaded for $language.") }
        }
    }
}
