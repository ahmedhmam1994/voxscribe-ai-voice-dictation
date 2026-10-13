package com.voxscribe.android

import android.content.Context

/** What a finished utterance turned into. */
sealed interface Spoken {
    /** Text to type. May be empty when nothing was recognized. */
    data class Text(val text: String) : Spoken

    /** A spoken editing command: remove some of what was typed last. */
    data class Edit(val edit: VoiceCommands.Edit) : Spoken

    /** A template is waiting for the answer to [slot]. */
    data class TemplatePrompt(val name: String, val slot: String) : Spoken

    /** A template was cancelled by voice. */
    data object TemplateCancelled : Spoken
}

/** Everything the text pipeline needs to know, apart from the audio. */
data class TextOptions(
    val pro: Boolean,
    val cleanup: Boolean,
    val voiceCommands: Boolean,
    val smartFormat: Boolean,
    val codeDictation: Boolean,
    val replacements: List<Pair<String, String>> = emptyList(),
    val snippets: List<Snippet> = emptyList(),
    val templates: List<Template> = emptyList(),
)

/**
 * Turns a raw transcript into the text to type, in the same order as the
 * Windows app: editing commands, then templates, then either code dictation
 * or (cleanup, voice commands, smart formatting), then word replacements and
 * snippets. Code dictation, smart formatting, templates and profiles are Pro.
 */
object TextPipeline {

    /** How long a half filled template waits for the next answer before it is dropped. */
    private const val TEMPLATE_TIMEOUT_MS = 120_000L

    /** The template being filled by voice, if any. Shared, since one person dictates at a time. */
    class TemplateState {
        var session: Templates.Session? = null
        var lastTurnAtMs: Long = 0
    }

    val templateState = TemplateState()

    fun process(
        raw: String,
        options: TextOptions,
        interactive: Boolean = false,
        state: TemplateState = templateState,
        nowMs: Long = System.currentTimeMillis(),
    ): Spoken {
        var text = raw
        if (interactive && text.isNotEmpty() && options.voiceCommands) {
            VoiceCommands.editingCommand(text)?.let { return Spoken.Edit(it) }
        }
        if (interactive && text.isNotEmpty() && options.pro) {
            templateTurn(text, options, state, nowMs)?.let { return it }
        }

        if (text.isNotEmpty() && options.pro && options.codeDictation) {
            // Code is not prose: no capitals, no full stops, no filler cleanup.
            text = CodeDictation.toCode(text)
        } else {
            if (text.isNotEmpty() && options.cleanup) text = TranscriptCleanup.clean(text)
            if (text.isNotEmpty() && options.voiceCommands) text = VoiceCommands.apply(text)
            if (text.isNotEmpty() && options.pro && options.smartFormat) text = SmartFormat.format(text)
        }
        if (text.isNotEmpty()) text = Replacements.apply(text, options.replacements)
        if (text.isNotEmpty() && options.pro) text = SnippetExpander.expand(text, options.snippets)
        return Spoken.Text(text)
    }

    /** Starts a spoken template or takes the next answer for one. Null when the utterance is not for a template. */
    private fun templateTurn(text: String, options: TextOptions, state: TemplateState, nowMs: Long): Spoken? {
        var session = state.session
        if (session != null && nowMs - state.lastTurnAtMs > TEMPLATE_TIMEOUT_MS) {
            session = null
            state.session = null
        }

        if (session == null) {
            val template = Templates.find(text, options.templates) ?: return null
            session = Templates.Session(template)
            if (session.finished) return Spoken.Text(session.result())
            state.session = session
        } else if (session.feed(text) == "cancel") {
            state.session = null
            return Spoken.TemplateCancelled
        }

        state.lastTurnAtMs = nowMs
        if (session.finished) {
            state.session = null
            return Spoken.Text(session.result())
        }
        return Spoken.TemplatePrompt(session.name, session.prompt.orEmpty())
    }

    /** The options for dictating right now, with the focused app's profile applied. */
    fun optionsFor(context: Context, packageName: String?): TextOptions {
        val pro = LicenseStore.isPro(context)
        val saved = TextToolsStore.snapshot(context)
        val profile = if (pro) {
            AppProfiles.optionsFor(AppProfiles.parseLines(saved.profiles), packageName)
        } else {
            emptyMap()
        }
        return TextOptions(
            pro = pro,
            cleanup = profile["cleanup"] ?: SettingsStore.cleanupEnabled(context),
            voiceCommands = profile["voice_commands"] ?: saved.voiceCommands,
            smartFormat = profile["smart"] ?: saved.smartFormat,
            codeDictation = profile["code"] ?: saved.codeDictation,
            replacements = Replacements.parse(saved.replacements),
            snippets = if (pro) SnippetStore.all(context) else emptyList(),
            templates = if (pro) Templates.parseLines(saved.templates) else emptyList(),
        )
    }
}
