package com.voxscribe.android

import android.content.Context

/**
 * The saved settings for the text tools: voice commands, word replacements,
 * smart formatting, code dictation, fill-in templates and per-app profiles.
 * Lists are kept as the same plain text the settings screen edits.
 */
object TextToolsStore {
    private const val PREFS_NAME = "voxscribe_texttools"
    private const val KEY_VOICE_COMMANDS = "voice_commands"
    private const val KEY_SEND_IT = "send_it"
    private const val KEY_SMART_FORMAT = "smart_format"
    private const val KEY_CODE_DICTATION = "code_dictation"
    private const val KEY_REPLACEMENTS = "replacements"
    private const val KEY_TEMPLATES = "templates"
    private const val KEY_PROFILES = "profiles"
    private const val KEY_MODE = "mode"
    private const val KEY_AUTO_MODES = "auto_modes"
    private const val KEY_TERM_PACKS = "term_packs"
    private const val KEY_SPOKEN_FORMATS = "spoken_formats"
    private const val KEY_READ_BACK = "read_back"
    private const val KEY_FORM_FILL = "form_fill"
    private const val KEY_SCREEN_SPELLING = "screen_spelling"
    private const val KEY_LEARN_FIXES = "learn_fixes"

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    /** Everything the settings screen shows, as one snapshot. */
    data class Snapshot(
        val voiceCommands: Boolean,
        val smartFormat: Boolean,
        val codeDictation: Boolean,
        val replacements: String,
        val templates: String,
        val profiles: String,
        val sendIt: Boolean = false,
        val mode: String = Modes.DEFAULT,
        val autoModes: Boolean = true,
        /** The term pack ids switched on, comma separated (see [TermPackStore]). */
        val termPacks: String = "",
        /** Doses, references and amounts for the packs that are on. Off by default. */
        val spokenFormats: Boolean = false,
        /** Read each dictation from the floating button aloud. Off by default. */
        val readBack: Boolean = false,
        /** Speak once, fill the whole form (see [FormFill]). On by default. */
        val formFill: Boolean = true,
        /** Names on screen fix how they are spelled (see [ScreenWords]). On by default. */
        val screenSpelling: Boolean = true,
        /** A word you fix after it is typed is spelled your way from then on (see [LearnedWords]). On by default. */
        val learnFixes: Boolean = true,
    )

    fun snapshot(context: Context): Snapshot {
        val p = prefs(context)
        return Snapshot(
            voiceCommands = p.getBoolean(KEY_VOICE_COMMANDS, false),
            smartFormat = p.getBoolean(KEY_SMART_FORMAT, false),
            codeDictation = p.getBoolean(KEY_CODE_DICTATION, false),
            replacements = p.getString(KEY_REPLACEMENTS, "").orEmpty(),
            templates = p.getString(KEY_TEMPLATES, "").orEmpty(),
            profiles = p.getString(KEY_PROFILES, "").orEmpty(),
            sendIt = p.getBoolean(KEY_SEND_IT, false),
            mode = p.getString(KEY_MODE, Modes.DEFAULT) ?: Modes.DEFAULT,
            autoModes = p.getBoolean(KEY_AUTO_MODES, true),
            termPacks = p.getString(KEY_TERM_PACKS, "").orEmpty(),
            spokenFormats = p.getBoolean(KEY_SPOKEN_FORMATS, false),
            readBack = p.getBoolean(KEY_READ_BACK, false),
            formFill = p.getBoolean(KEY_FORM_FILL, true),
            screenSpelling = p.getBoolean(KEY_SCREEN_SPELLING, true),
            learnFixes = p.getBoolean(KEY_LEARN_FIXES, true),
        )
    }

    fun save(context: Context, snapshot: Snapshot) {
        prefs(context).edit()
            .putBoolean(KEY_VOICE_COMMANDS, snapshot.voiceCommands)
            .putBoolean(KEY_SMART_FORMAT, snapshot.smartFormat)
            .putBoolean(KEY_CODE_DICTATION, snapshot.codeDictation)
            .putString(KEY_REPLACEMENTS, snapshot.replacements)
            .putString(KEY_TEMPLATES, snapshot.templates)
            .putString(KEY_PROFILES, snapshot.profiles)
            .putBoolean(KEY_SEND_IT, snapshot.sendIt)
            .putString(KEY_MODE, snapshot.mode)
            .putBoolean(KEY_AUTO_MODES, snapshot.autoModes)
            .putString(KEY_TERM_PACKS, snapshot.termPacks)
            .putBoolean(KEY_SPOKEN_FORMATS, snapshot.spokenFormats)
            .putBoolean(KEY_READ_BACK, snapshot.readBack)
            .putBoolean(KEY_FORM_FILL, snapshot.formFill)
            .putBoolean(KEY_SCREEN_SPELLING, snapshot.screenSpelling)
            .putBoolean(KEY_LEARN_FIXES, snapshot.learnFixes)
            .apply()
    }
}
