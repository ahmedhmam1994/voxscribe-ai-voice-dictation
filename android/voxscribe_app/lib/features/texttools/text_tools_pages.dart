import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/pro/pro_controller.dart';
import 'package:voxscribe_app/features/settings/widgets/settings_group.dart';
import 'package:voxscribe_app/features/texttools/domain/word_lists.dart';
import 'package:voxscribe_app/features/texttools/text_tools_controller.dart';
import 'package:voxscribe_app/shared/widgets/section_label.dart';
import 'package:voxscribe_app/shared/widgets/vox_card.dart';

/// How many `left => right` rules a list holds, for the Settings summaries.
int ruleCount(String text) => parseReplacementsText(text).length;

/// The pages Settings opens for each text tool. Each one explains its feature
/// in full, so the Settings screen itself can stay short.

/// Every spoken command, grouped by what it does, and the switch for them.
class VoiceCommandsPage extends StatelessWidget {
  const VoiceCommandsPage({required this.controller, super.key});

  final TextToolsController controller;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context).textTheme;
    return _ToolScaffold(
      title: 'Voice commands',
      listenable: controller,
      builder: (context) => [
        Text(
          'Say these while you dictate and VoxScribe acts on them instead of '
          'typing the words. Off by default, because someone who says the '
          'word "period" may mean the word.',
          style: theme.bodyMedium,
        ),
        const SizedBox(height: 16),
        SettingsGroup(
          label: 'Switch',
          children: [
            SettingsSwitchRow(
              title: 'Voice commands',
              subtitle: 'Turns on every command on this page.',
              value: controller.settings.voiceCommands,
              onChanged: (value) => controller.setVoiceCommands(value: value),
            ),
          ],
        ),
        const _CommandList(
          label: 'Punctuation',
          commands: [
            ('"period" or "full stop"', '.'),
            ('"comma"', ','),
            ('"question mark"', '?'),
            ('"exclamation mark"', '!'),
            ('"colon" / "semicolon"', ': ;'),
            ('"open quote" / "close quote"', '" "'),
            ('"open paren" / "close paren"', '( )'),
            ('"new line"', 'a line break'),
            ('"new paragraph"', 'an empty line'),
          ],
        ),
        const _CommandList(
          label: 'Take it back',
          commands: [
            ('"scratch that"', 'removes your last dictation'),
            ('"delete last word"', 'removes one word'),
            ('"delete last sentence"', 'removes one sentence'),
          ],
        ),
        const _CommandList(
          label: 'Change it',
          commands: [
            ('"capitalize that"', 'Capitals On Each Word'),
            ('"all caps"', 'ALL CAPITALS'),
            ('"lowercase that"', 'all small letters'),
            ('"replace noon with one"', 'swaps a word'),
          ],
        ),
        const SizedBox(height: 12),
        _Note(
          'Say a command on its own to change what you dictated last, or at '
          'the end of the same sentence after a short pause: "bring the notes, '
          'all caps". Commands work in the box you dictated into, as long as '
          'it still ends with what VoxScribe typed.',
        ),
      ],
    );
  }
}

/// The opt-in "send it" command, with how it works and what it reads.
class SendItPage extends StatelessWidget {
  const SendItPage({required this.controller, super.key});

  final TextToolsController controller;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context).textTheme;
    return _ToolScaffold(
      title: 'Send it',
      listenable: controller,
      builder: (context) => [
        Text(
          'Send a message without touching the screen. Off by default, because '
          'it sends for you.',
          style: theme.bodyMedium,
        ),
        const SizedBox(height: 16),
        SettingsGroup(
          label: 'Switch',
          children: [
            SettingsSwitchRow(
              title: 'Say "send it" to send',
              subtitle: 'Needs Android 11 or newer.',
              value: controller.settings.sendIt,
              onChanged: (value) => controller.setSendIt(value: value),
            ),
          ],
        ),
        const _CommandList(
          label: 'What to say',
          commands: [
            ('"How are you? Send it."', 'types the message, then sends it'),
            ('"send it" on its own', 'sends what is in the box'),
            ('"press enter"', 'presses the Enter key'),
          ],
        ),
        const SizedBox(height: 12),
        _Note(
          'VoxScribe taps the app\'s own Send button, because in most chat '
          'apps Enter only adds a new line. When there is no Send button, as '
          'in a search box, it presses Enter. To find the button it reads '
          'button names only, never your messages, and it does nothing in a '
          'password box. Say "send it" after a pause, so "please send it to '
          'Sam" stays part of your message.',
        ),
      ],
    );
  }
}

/// The word replacements editor, with import, export and the Fix a word tip.
class ReplacementsPage extends StatelessWidget {
  const ReplacementsPage({required this.controller, super.key});

  final TextToolsController controller;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context).textTheme;
    return _ToolScaffold(
      title: 'Word replacements',
      listenable: controller,
      builder: (context) => [
        Text(
          'Fix a word the model keeps getting wrong the same way, such as a '
          'name. Free, and applied to every dictation.',
          style: theme.bodyMedium,
        ),
        const SizedBox(height: 16),
        if (controller.loaded)
          NoteField(
            key: ValueKey('replacements-${controller.replacementsRevision}'),
            label: 'Heard => replacement',
            hint: 'vox scribe => VoxScribe',
            help:
                'One per line. Whole words only, not case sensitive. Leave the '
                'right side empty to delete a word.',
            initial: controller.settings.replacements,
            onChanged: controller.setReplacements,
          ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            OutlinedButton.icon(
              onPressed: () => _report(context, controller.importWordLists()),
              icon: const Icon(Icons.file_open_outlined, size: 18),
              label: const Text('Import'),
            ),
            OutlinedButton.icon(
              onPressed: () => _report(context, controller.exportWordLists()),
              icon: const Icon(Icons.save_alt, size: 18),
              label: const Text('Export'),
            ),
          ],
        ),
        const SizedBox(height: 4),
        Text(
          'One file for a backup, another phone or the Windows app.',
          style: theme.bodySmall,
        ),
        const SizedBox(height: 16),
        _Note(
          'Quicker: on the Dictation screen, tap "Fix a word" under a '
          'dictation, pick the word that was wrong and type what it should '
          'be. It is added here for you.',
        ),
      ],
    );
  }
}

/// Fill-in templates (Pro).
class TemplatesPage extends StatelessWidget {
  const TemplatesPage({required this.controller, required this.pro, super.key});

  final TextToolsController controller;
  final ProController pro;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context).textTheme;
    return _ToolScaffold(
      title: 'Fill-in templates',
      listenable: Listenable.merge([controller, pro]),
      builder: (context) => [
        Text(
          'Say "template bug report" and VoxScribe asks for each part in turn, '
          'then types the whole thing.',
          style: theme.bodyMedium,
        ),
        if (!pro.isPro) const _ProLocked(),
        const SizedBox(height: 16),
        if (controller.loaded)
          NoteField(
            label: 'Name => text with {slots}',
            hint: r'bug report => Title: {title}\nSteps: {steps}',
            help:
                r'One per line. Use \n for a line break. Say "skip" to leave a '
                'slot empty or "cancel" to stop. {date} and {time} fill '
                'themselves in.',
            initial: controller.settings.templates,
            enabled: pro.isPro,
            onChanged: controller.setTemplates,
          ),
      ],
    );
  }
}

/// Per-app profiles (Pro).
class ProfilesPage extends StatelessWidget {
  const ProfilesPage({required this.controller, required this.pro, super.key});

  final TextToolsController controller;
  final ProController pro;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context).textTheme;
    return _ToolScaffold(
      title: 'Per-app profiles',
      listenable: Listenable.merge([controller, pro]),
      builder: (context) => [
        Text(
          'Dictate differently in different apps, for example code in a '
          'terminal and plain text everywhere else.',
          style: theme.bodyMedium,
        ),
        if (!pro.isPro) const _ProLocked(),
        const SizedBox(height: 16),
        if (controller.loaded)
          NoteField(
            label: 'App package => options',
            hint: 'com.termux => code=on, cleanup=off',
            help:
                "One per line, using the app's package name. Options: mode "
                '(chat, email, code, notes or default), and cleanup, '
                'voice_commands, code, smart and period, each on or off. '
                'Anything not set uses the mode, then your normal settings.',
            initial: controller.settings.profiles,
            enabled: pro.isPro,
            onChanged: controller.setProfiles,
          ),
      ],
    );
  }
}

/// Names and one-line descriptions of the dictation modes, in display order.
const dictationModes = <(String, String, String)>[
  ('default', 'Default', 'Your settings exactly as they are.'),
  ('chat', 'Chat', 'Tidy text, no full stop at the end of a one-line message.'),
  ('email', 'Email', 'Full sentences with punctuation.'),
  ('code', 'Code', 'Code dictation. Pro.'),
  ('notes', 'Notes', 'Tidy text, nothing rewritten.'),
];

String modeName(String mode) =>
    dictationModes.firstWhere((m) => m.$1 == mode, orElse: () => dictationModes.first).$2;

/// Pick the dictation mode, and (Pro) let it switch with the app in front.
class ModesPage extends StatelessWidget {
  const ModesPage({required this.controller, required this.pro, super.key});

  final TextToolsController controller;
  final ProController pro;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context).textTheme;
    return _ToolScaffold(
      title: 'Dictation mode',
      listenable: Listenable.merge([controller, pro]),
      builder: (context) {
        final settings = controller.settings;
        return [
          Text(
            'A mode sets how your words are tidied up, to match what you are '
            'writing.',
            style: theme.bodyMedium,
          ),
          const SizedBox(height: 12),
          RadioGroup<String>(
            groupValue: settings.mode,
            onChanged: (value) {
              if (value != null) controller.setMode(value);
            },
            child: Column(
              children: [
                for (final (id, name, description) in dictationModes)
                  ProGate(
                    unlocked: id != 'code' || pro.isPro,
                    child: RadioListTile<String>(
                      value: id,
                      title: Text(name),
                      subtitle: Text(description),
                      contentPadding: EdgeInsets.zero,
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 8),
          ProGate(
            unlocked: pro.isPro,
            child: SwitchListTile(
              value: settings.autoModes,
              onChanged: (value) => controller.setAutoModes(value: value),
              title: const Text('Switch by app automatically (Pro)'),
              subtitle: const Text(
                'Chat apps use Chat, mail apps use Email, Termux uses Code, '
                'and Keep, Notion, Obsidian and Word use Notes. Every other '
                'app uses the mode above.',
              ),
              contentPadding: EdgeInsets.zero,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Decided from the app name only. VoxScribe never reads your screen.',
            style: theme.bodySmall,
          ),
        ];
      },
    );
  }
}

/// Greys out and blocks a Pro row while Pro is locked.
class ProGate extends StatelessWidget {
  const ProGate({required this.unlocked, required this.child, super.key});

  final bool unlocked;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    if (unlocked) return child;
    return Opacity(opacity: 0.5, child: IgnorePointer(child: child));
  }
}

/// A multi line box that keeps its own text and reports every change.
class NoteField extends StatefulWidget {
  const NoteField({
    required this.label,
    required this.hint,
    required this.help,
    required this.initial,
    required this.onChanged,
    this.enabled = true,
    super.key,
  });

  final String label;
  final String hint;
  final String help;
  final String initial;
  final bool enabled;
  final ValueChanged<String> onChanged;

  @override
  State<NoteField> createState() => _NoteFieldState();
}

class _NoteFieldState extends State<NoteField> {
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
            minLines: 4,
            maxLines: 12,
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

class _ToolScaffold extends StatelessWidget {
  const _ToolScaffold({
    required this.title,
    required this.listenable,
    required this.builder,
  });

  final String title;
  final Listenable listenable;
  final List<Widget> Function(BuildContext context) builder;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: ListenableBuilder(
        listenable: listenable,
        builder: (context, _) => ListView(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
          children: builder(context),
        ),
      ),
    );
  }
}

/// What to say on the left, what happens on the right.
class _CommandList extends StatelessWidget {
  const _CommandList({required this.label, required this.commands});

  final String label;
  final List<(String, String)> commands;

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    final theme = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionLabel(label),
        VoxCard(
          child: Column(
            children: [
              for (final (say, result) in commands)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        flex: 5,
                        child: Text(
                          say,
                          style: theme.bodyMedium?.copyWith(
                            color: c.text,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        flex: 4,
                        child: Text(
                          result,
                          style: theme.bodyMedium?.copyWith(color: c.muted),
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

class _Note extends StatelessWidget {
  const _Note(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(Icons.info_outline, size: 18, color: c.muted),
        const SizedBox(width: 8),
        Expanded(
          child: Text(text, style: Theme.of(context).textTheme.bodySmall),
        ),
      ],
    );
  }
}

class _ProLocked extends StatelessWidget {
  const _ProLocked();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: _Note(
        'Pro (locked). Unlock Pro in Settings with the same key as Windows to '
        'use this.',
      ),
    );
  }
}

/// Shows what an import or export did, unless the user backed out.
Future<void> _report(BuildContext context, Future<String?> outcome) async {
  final messenger = ScaffoldMessenger.of(context);
  final message = await outcome;
  if (message == null) return;
  messenger.showSnackBar(SnackBar(content: Text(message)));
}
