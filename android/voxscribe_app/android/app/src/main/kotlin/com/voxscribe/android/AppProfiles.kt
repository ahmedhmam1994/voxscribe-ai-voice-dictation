package com.voxscribe.android

/**
 * Per-app profiles, a Pro feature: a profile changes a few dictation settings
 * for one app, so the same bubble does the right thing in each: code dictation
 * in a terminal app, no cleanup in notes, voice commands off in a chat app.
 *
 * Matched by the focused app's package name. Written in Settings as one line
 * per app, in the same style as the Windows app:
 *
 *     com.termux => code=on, cleanup=off
 *
 * The Windows app can also set a language per program. Here the speech model
 * is loaded for one language at a time, so switching it per app would stall
 * every change of app, and the option is not offered.
 */
object AppProfiles {
    /** The on or off options a profile may set. */
    val flagOptions = setOf("cleanup", "voice_commands", "code", "smart")

    private val on = setOf("on", "true", "yes", "1")
    private val off = setOf("off", "false", "no", "0")

    /** `package => option=value, ...` lines to {package: {option: on or off}}. Bad options and empty profiles are dropped. */
    fun parseLines(text: String): Map<String, Map<String, Boolean>> {
        val profiles = linkedMapOf<String, Map<String, Boolean>>()
        for (line in text.lines()) {
            val arrow = line.indexOf("=>")
            if (arrow < 0) continue
            val app = line.substring(0, arrow).trim().lowercase()
            if (app.isEmpty()) continue
            val flags = linkedMapOf<String, Boolean>()
            for (part in line.substring(arrow + 2).split(",")) {
                val equals = part.indexOf('=')
                if (equals < 0) continue
                val name = part.substring(0, equals).trim().lowercase()
                val value = part.substring(equals + 1).trim().lowercase()
                if (name in flagOptions && (value in on || value in off)) flags[name] = value in on
            }
            if (flags.isNotEmpty()) profiles[app] = flags
        }
        return profiles
    }

    /** The options set for this app, or an empty map when it has none. */
    fun optionsFor(profiles: Map<String, Map<String, Boolean>>, packageName: String?): Map<String, Boolean> =
        if (packageName.isNullOrEmpty()) emptyMap() else profiles[packageName.lowercase()] ?: emptyMap()
}
