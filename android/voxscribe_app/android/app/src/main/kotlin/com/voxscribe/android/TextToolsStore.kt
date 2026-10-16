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
            .apply()
    }
}
