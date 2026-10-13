import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/pro/pro_controller.dart';
import 'package:voxscribe_app/features/settings/widgets/settings_group.dart';
import 'package:voxscribe_app/features/texttools/text_tools_controller.dart';
import 'package:voxscribe_app/shared/widgets/section_label.dart';
import 'package:voxscribe_app/shared/widgets/vox_card.dart';

/// What happens to a transcript before it is typed: spoken punctuation, word
/// replacements, and the Pro tools (smart formatting, code dictation,
/// templates and per-app profiles).
class TextToolsPage extends StatelessWidget {
  const TextToolsPage({required this.controller, required this.pro, super.key});

  final TextToolsController controller;
  final ProController pro;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(title: const Text('Text tools')),
      body: ListenableBuilder(
        listenable: Listenable.merge([controller, pro]),
        builder: (context, _) {
          final values = controller.settings;
          final unlocked = pro.isPro;
          return ListView(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
            children: [
              Text(
                'These shape the text before it is typed. Everything runs '
                'on the phone.',
                style: theme.bodyMedium,
              ),
              const SizedBox(height: 16),
              SettingsGroup(
                label: 'Free',
                children: [
                  SettingsSwitchRow(
                    title: 'Voice commands',
                    subtitle:
                        'Say "period", "comma", "new line" or "question '
                        'mark" for the symbol. "Scratch that" and "delete '
                        'last word" take back what was typed.',
                    value: values.voiceCommands,
                    onChanged: (value) =>
                        controller.setVoiceCommands(value: value),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              const SectionLabel('Word replacements'),
              if (controller.loaded)
                _NoteField(
                  label: 'Heard => replacement',
                  hint: 'vox scribe => VoxScribe',
                  help:
                      'One per line. Fixes a word the model keeps getting '
                      'wrong. Whole words only, not case sensitive. Leave '
                      'the right side empty to delete a word.',
                  initial: values.replacements,
                  onChanged: controller.setReplacements,
                ),
              const SizedBox(height: 16),
              SettingsGroup(
                label: unlocked ? 'Pro' : 'Pro (locked)',
                children: [
                  _ProRow(
                    unlocked: unlocked,
                    child: SettingsSwitchRow(
                      title: 'Smart formatting',
                      subtitle:
                          '"john at gmail dot com" becomes john@gmail.com, '
                          '"twenty five percent" becomes 25%.',
                      value: values.smartFormat,
                      onChanged: (value) =>
                          controller.setSmartFormat(value: value),
                    ),
                  ),
                  _ProRow(
                    unlocked: unlocked,
                    child: SettingsSwitchRow(
                      title: 'Code dictation',
                      subtitle:
                          '"camel case user name" becomes userName. Turns off '
                          'capital letters and filler cleanup while on.',
                      value: values.codeDictation,
                      onChanged: (value) =>
                          controller.setCodeDictation(value: value),
                    ),
                  ),
                ],
              ),
              if (!unlocked) ...[
                const SizedBox(height: 8),
                Text(
                  'Unlock Pro with the same key as Windows to use these.',
                  style: theme.bodySmall,
                ),
              ],
              const SizedBox(height: 16),
              const SectionLabel('Fill-in templates (Pro)'),
              if (controller.loaded)
                _NoteField(
                  label: 'Name => text with {slots}',
                  hint: r'bug report => Title: {title}\nSteps: {steps}',
                  help:
                      r'One per line. Use \n for a line break. Say "template '
                      'bug report" and each slot is asked for in turn; say '
                      '"skip" to leave one empty or "cancel" to stop. {date} '
                      'and {time} fill themselves in.',
                  initial: values.templates,
                  enabled: unlocked,
                  onChanged: controller.setTemplates,
                ),
              const SizedBox(height: 16),
              const SectionLabel('Per-app profiles (Pro)'),
              if (controller.loaded)
                _NoteField(
                  label: 'App package => options',
                  hint: 'com.termux => code=on, cleanup=off',
                  help:
                      "One per line, using the app's package name. Options: "
                      'cleanup, voice_commands, code and smart, each on or '
                      'off. Applies while that app has focus; anything not '
                      'set uses your normal settings.',
                  initial: values.profiles,
                  enabled: unlocked,
                  onChanged: controller.setProfiles,
                ),
            ],
          );
        },
      ),
    );
  }
}

/// Greys out and blocks a Pro row while Pro is locked.
class _ProRow extends StatelessWidget {
  const _ProRow({required this.unlocked, required this.child});

  final bool unlocked;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    if (unlocked) return child;
    return Opacity(opacity: 0.5, child: IgnorePointer(child: child));
  }
}

/// A multi line box that keeps its own text and reports every change.
class _NoteField extends StatefulWidget {
  const _NoteField({
    required this.label,
    required this.hint,
    required this.help,
    required this.initial,
    required this.onChanged,
    this.enabled = true,
  });

  final String label;
  final String hint;
  final String help;
  final String initial;
  final bool enabled;
  final ValueChanged<String> onChanged;

  @override
  State<_NoteField> createState() => _NoteFieldState();
}

class _NoteFieldState extends State<_NoteField> {
  late final TextEditingController _text = TextEditingController(
    text: widget.initial,
  );

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    final theme = Theme.of(context).textTheme;
    return VoxCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          TextField(
            controller: _text,
            enabled: widget.enabled,
            minLines: 3,
            maxLines: 8,
            keyboardType: TextInputType.multiline,
            autocorrect: false,
            enableSuggestions: false,
            onChanged: widget.onChanged,
            decoration: InputDecoration(
              labelText: widget.label,
              hintText: widget.hint,
              hintStyle: TextStyle(color: c.muted),
            ),
          ),
          const SizedBox(height: 8),
          Text(widget.help, style: theme.bodySmall),
        ],
      ),
    );
  }
}
