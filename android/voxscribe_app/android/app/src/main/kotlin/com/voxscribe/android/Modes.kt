package com.voxscribe.android

/**
 * Dictation modes, the same four as the Windows app: ready-made bundles of
 * the per-app profile options, so the same button writes the way each kind
 * of app expects.
 *
 * - Chat: cleanup and smart formatting, and no full stop at the end of a
 *   one-sentence message, the way people type in chats.
 * - Email: cleanup, spoken punctuation and smart formatting.
 * - Code: code dictation (Pro), no cleanup, no smart formatting.
 * - Notes: cleanup and spoken punctuation, nothing rewritten.
 *
 * Free: one mode for every app. Pro: the mode switches with the focused app
 * ([autoModes]), and a profile line can pick one with `mode=chat`. Decided
 * from the app's package name only; VoxScribe never reads the screen.
 */
object Modes {
    const val DEFAULT = "default"

    val options: Map<String, Map<String, Boolean>> = mapOf(
        DEFAULT to emptyMap(),
        "chat" to mapOf("cleanup" to true, "voice_commands" to true, "smart" to true, "period" to false),
        "email" to mapOf("cleanup" to true, "voice_commands" to true, "smart" to true, "period" to true),
        "code" to mapOf("code" to true, "cleanup" to false, "smart" to false),
        "notes" to mapOf("cleanup" to true, "voice_commands" to true, "smart" to false, "period" to true),
    )

    val proModes = setOf("code")

    /** Package name to mode, used when automatic switching is on (Pro). Browsers are left out on purpose. */
    val autoModes: Map<String, String> = mapOf(
        // Chat
        "com.whatsapp" to "chat",
        "com.whatsapp.w4b" to "chat",
        "org.telegram.messenger" to "chat",
        "org.thoughtcrime.securesms" to "chat",
        "com.facebook.orca" to "chat",
        "com.discord" to "chat",
        "com.Slack" to "chat",
        "com.slack" to "chat",
        "com.microsoft.teams" to "chat",
        "com.google.android.apps.messaging" to "chat",
        "com.samsung.android.messaging" to "chat",
        "com.viber.voip" to "chat",
        // Email
        "com.google.android.gm" to "email",
        "com.microsoft.office.outlook" to "email",
        "com.samsung.android.email.provider" to "email",
        "ch.protonmail.android" to "email",
        "net.thunderbird.android" to "email",
        "com.fsck.k9" to "email",
        // Code
        "com.termux" to "code",
        "com.foxdebug.acode" to "code",
        // Notes
        "com.google.android.keep" to "notes",
        "com.samsung.android.app.notes" to "notes",
        "md.obsidian" to "notes",
        "notion.id" to "notes",
        "com.microsoft.office.word" to "notes",
        "com.microsoft.office.onenote" to "notes",
        "com.evernote" to "notes",
        "com.google.android.apps.docs.editors.docs" to "notes",
    ).mapKeys { it.key.lowercase() }

    /** Which mode applies in this app. */
    fun modeFor(packageName: String?, profileMode: String?, globalMode: String, autoSwitch: Boolean, pro: Boolean): String {
        var mode = if (globalMode in options) globalMode else DEFAULT
        if (pro) {
            val app = packageName?.lowercase()
            if (autoSwitch && app != null) autoModes[app]?.let { mode = it }
            if (profileMode != null && profileMode in options) mode = profileMode
        }
        if (mode in proModes && !pro) mode = DEFAULT
        return mode
    }

    private val abbreviations = setOf("etc", "e.g", "i.e", "vs", "inc", "ltd", "jr", "sr", "dr", "mr", "mrs", "ms")

    /** "See you at 5." becomes "See you at 5", only for a single sentence; "etc." and "..." stay. */
    fun dropFinalPeriod(text: String): String {
        val stripped = text.trimEnd()
        if (!stripped.endsWith(".") || stripped.endsWith("..")) return text
        val body = stripped.dropLast(1)
        if (listOf(". ", "! ", "? ", "\n").any { it in body }) return text
        if (body.substringAfterLast(' ').lowercase() in abbreviations) return text
        return body + text.substring(stripped.length)
    }
}
