package com.voxscribe.android

import android.content.Context
import android.util.Log
import com.k2fsa.sherpa.onnx.FeatureConfig
import com.k2fsa.sherpa.onnx.OfflineModelConfig
import com.k2fsa.sherpa.onnx.OfflineRecognizer
import com.k2fsa.sherpa.onnx.OfflineRecognizerConfig
import com.k2fsa.sherpa.onnx.OfflineWhisperModelConfig

/**
 * MILESTONE 2: bundled, on-device Whisper transcription via sherpa-onnx, so
 * VoxScribe-Android no longer has to depend on the phone's OS-level offline
 * speech-recognition language pack the way Milestone 1's SpeechRecognizer
 * does -- this is the closer match to how the desktop app bundles
 * faster-whisper itself.
 *
 * Requires two things this repo deliberately does NOT commit (see
 * android/VoxScribeAndroid/.gitignore and README-ANDROID.md's "Milestone 2:
 * getting the pieces" -- both are binaries nobody can meaningfully diff):
 *   1. app/libs/sherpa-onnx-1.13.6.aar
 *   2. app/src/main/assets/whisper/{tiny.en-encoder.int8.onnx,
 *      tiny.en-decoder.int8.onnx, tiny.en-tokens.txt}
 *
 * If either is missing, [isAvailable] returns false and
 * VoxScribeInputMethodService falls back to Milestone 1's SpeechRecognizer
 * path -- this never crashes the app for someone who hasn't done that
 * manual setup yet.
 *
 * NOT build-verified. This was written by cross-referencing sherpa-onnx's
 * own published Kotlin API source (OfflineRecognizer.kt, OfflineStream.kt,
 * FeatureConfig.kt) and its official Android demo apps in the k2-fsa/
 * sherpa-onnx repo -- not guessed API surface -- but there is no Android
 * SDK/emulator in the environment this was written in to actually compile
 * and run it. Treat the first real build as the real test, not this
 * comment.
 */
object WhisperEngine {
    private const val TAG = "WhisperEngine"
    private const val ASSET_DIR = "whisper"
    private const val ENCODER = "tiny.en-encoder.int8.onnx"
    private const val DECODER = "tiny.en-decoder.int8.onnx"
    private const val TOKENS = "tiny.en-tokens.txt"

    /** sherpa-onnx's FeatureConfig/OfflineStream both expect 16kHz audio. */
    const val SAMPLE_RATE = 16000

    private var recognizer: OfflineRecognizer? = null
    private var checkedAvailability = false
    private var available = false
    private var loadError: String? = null
    private var assetFilesFound: Set<String> = emptySet()

    /** True once the bundled model assets are present and the recognizer loaded. */
    fun isAvailable(context: Context): Boolean {
        ensureInitialized(context)
        return available
    }

    /**
     * Multi-line human-readable status for the Settings/diagnostics screen --
     * which files are present, whether the recognizer actually loaded, and
     * the load exception's message if it didn't.
     */
    fun statusDescription(context: Context): String {
        ensureInitialized(context)
        val required = listOf(ENCODER, DECODER, TOKENS)
        val missing = required.filterNot { it in assetFilesFound }
        return buildString {
            if (missing.isEmpty()) {
                append("Model files: all present\n")
            } else {
                append("Model files: missing ${missing.joinToString(", ")}\n")
            }
            append(
                when {
                    available -> "Recognizer: loaded, ready"
                    missing.isNotEmpty() -> "Recognizer: not loaded (missing files above)"
                    loadError != null -> "Recognizer: failed to load -- $loadError"
                    else -> "Recognizer: not loaded"
                }
            )
        }
    }

    private fun ensureInitialized(context: Context) {
        if (checkedAvailability) return
        checkedAvailability = true

        assetFilesFound = try {
            context.assets.list(ASSET_DIR)?.toSet() ?: emptySet()
        } catch (e: Exception) {
            emptySet()
        }
        if (!assetFilesFound.containsAll(listOf(ENCODER, DECODER, TOKENS))) {
            Log.i(
                TAG,
                "Whisper model assets not found under assets/$ASSET_DIR -- " +
                    "falling back to SpeechRecognizer. See README-ANDROID.md Milestone 2."
            )
            return
        }

        try {
            val config = OfflineRecognizerConfig(
                featConfig = FeatureConfig(sampleRate = SAMPLE_RATE, featureDim = 80),
                modelConfig = OfflineModelConfig(
                    whisper = OfflineWhisperModelConfig(
                        encoder = "$ASSET_DIR/$ENCODER",
                        decoder = "$ASSET_DIR/$DECODER",
                        language = "en",
                        task = "transcribe",
                    ),
                    tokens = "$ASSET_DIR/$TOKENS",
                    numThreads = 2,
                    provider = "cpu",
                ),
            )
            recognizer = OfflineRecognizer(context.assets, config)
            available = true
            Log.i(TAG, "Whisper (sherpa-onnx) recognizer loaded from bundled assets.")
        } catch (e: Exception) {
            // A real device/library mismatch (wrong AAR version, corrupt model
            // file, unsupported ABI) surfaces here as an exception from the
            // native layer -- fail closed to the fallback path rather than
            // leaving the IME stuck in a broken state.
            Log.e(TAG, "Failed to load bundled Whisper model, falling back to SpeechRecognizer", e)
            loadError = e.message ?: e.javaClass.simpleName
            recognizer = null
            available = false
        }
    }

    /**
     * Blocking and CPU-bound -- always call from a background thread, never
     * the main thread that owns the IME's InputConnection.
     */
    fun transcribe(samples: FloatArray): String {
        val r = recognizer ?: return ""
        val stream = r.createStream()
        try {
            stream.acceptWaveform(samples, SAMPLE_RATE)
            r.decode(stream)
            return r.getResult(stream).text
        } finally {
            stream.release()
        }
    }
}
