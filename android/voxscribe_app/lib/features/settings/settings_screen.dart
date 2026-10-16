import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/dictation/dictation_controller.dart';
import 'package:voxscribe_app/features/dictation/domain/dictation_language.dart';
import 'package:voxscribe_app/features/dictation/widgets/language_picker.dart';
import 'package:voxscribe_app/features/history/history_controller.dart';
import 'package:voxscribe_app/features/pro/pro_controller.dart';
import 'package:voxscribe_app/features/pro/pro_page.dart';
import 'package:voxscribe_app/features/settings/domain/app_settings.dart';
import 'package:voxscribe_app/features/settings/settings_controller.dart';
import 'package:voxscribe_app/features/settings/widgets/settings_group.dart';
import 'package:voxscribe_app/features/setup/domain/setup_status.dart';
import 'package:voxscribe_app/features/setup/setup_controller.dart';
import 'package:voxscribe_app/features/setup/setup_page.dart';
import 'package:voxscribe_app/features/snippets/snippets_controller.dart';
import 'package:voxscribe_app/features/texttools/text_tools_controller.dart';
import 'package:voxscribe_app/features/texttools/text_tools_pages.dart';
import 'package:voxscribe_app/shared/widgets/brand_mark.dart';

/// Every setting, in groups: setup, Pro, dictation, voice commands, word
/// replacements, the Pro tools, appearance, and privacy and data.
class SettingsScreen extends StatelessWidget {
  const SettingsScreen({
    required this.settings,
    required this.setup,
    required this.dictation,
    required this.history,
    required this.pro,
    required this.snippets,
    required this.textTools,
    this.openLink,
    super.key,
  });

  final SettingsController settings;
  final SetupController setup;
  final DictationController dictation;
  final HistoryController history;
  final ProController pro;
  final SnippetsController snippets;
  final TextToolsController textTools;

  /// Opens a web page in the browser. Null hides the links.
  final Future<void> Function(String url)? openLink;

  static const _privacyUrl =
      'https://voxscribe-ai-voice-dictation.vercel.app/privacy-at-a-glance.html';

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: Listenable.merge([
        settings,
        setup,
        dictation,
        pro,
        textTools,
      ]),
      builder: (context, _) {
        final values = settings.settings;
        final tools = textTools.settings;
        final unlocked = pro.isPro;
        return Column(
          children: [
            const _Header(),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
                children: [
                  Text(
                    'Settings',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  SettingsGroup(
                    label: 'Setup',
                    children: [
                      SettingsRow(
                        title: 'Floating button and permissions',
                        subtitle: _setupSummary(setup.status),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => _openSetup(context),
                      ),
                    ],
                  ),
                  SettingsGroup(
                    label: 'Dictation',
                    children: [
                      SettingsRow(
                        title: 'Language you speak',
                        trailing: Text(
                          languageForCode(dictation.language).name,
                          style: Theme.of(context).textTheme.bodyMedium
                              ?.copyWith(color: context.vox.muted),
                        ),
                        onTap: dictation.canStart
                            ? () => _chooseLanguage(context)
                            : null,
                      ),
                      SettingsSwitchRow(
                        title: 'Remove filler words',
                        subtitle: 'Takes out "um", "uh" and repeated words.',
                        value: values.cleanup,
                        onChanged: (value) => settings.setCleanup(value: value),
                      ),
                      SettingsSwitchRow(
                        title: 'Add a space after dictated text',
                        subtitle: 'So the next dictation does not run into it.',
                        value: values.trailingSpace,
                        onChanged: (value) =>
                            settings.setTrailingSpace(value: value),
                      ),
                    ],
                  ),
                  SettingsGroup(
                    label: 'Voice commands',
                    children: [
                      SettingsRow(
                        title: 'Voice commands',
                        subtitle: tools.voiceCommands
                            ? 'On. Punctuation, take back, change it.'
                            : 'Off. Say "period", "scratch that", "all caps".',
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => _push(
                          context,
                          VoiceCommandsPage(controller: textTools),
                        ),
                      ),
                      SettingsRow(
                        title: 'Say "send it" to send',
                        subtitle: tools.sendIt
                            ? 'On. Taps the Send button for you.'
                            : 'Off. Send a message by voice.',
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () =>
                            _push(context, SendItPage(controller: textTools)),
                      ),
                    ],
                  ),
                  SettingsGroup(
                    label: 'Word replacements',
                    children: [
                      SettingsRow(
                        title: 'Your replacements',
                        subtitle: _countLine(
                          ruleCount(tools.replacements),
                          'replacement',
                          'Fix words the model keeps getting wrong.',
                        ),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => _push(
                          context,
                          ReplacementsPage(controller: textTools),
                        ),
                      ),
                    ],
                  ),
                  SettingsGroup(
                    label: 'VoxScribe Pro',
                    children: [
                      SettingsRow(
                        title: 'VoxScribe Pro',
                        subtitle: unlocked
                            ? 'Unlocked. Snippets and the tools below are on.'
                            : 'Locked. Unlock snippets and the tools below '
                                  'with the same key as Windows.',
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => _openPro(context),
                      ),
                      ProGate(
                        unlocked: unlocked,
                        child: SettingsSwitchRow(
                          title: 'Smart formatting',
                          subtitle:
                              '"john at gmail dot com" becomes john@gmail.com, '
                              '"twenty five percent" becomes 25%.',
                          value: tools.smartFormat,
                          onChanged: (value) =>
                              textTools.setSmartFormat(value: value),
                        ),
                      ),
                      ProGate(
                        unlocked: unlocked,
                        child: SettingsSwitchRow(
                          title: 'Code dictation',
                          subtitle:
                              '"camel case user name" becomes userName. Turns '
                              'off capitals and filler cleanup while on.',
                          value: tools.codeDictation,
                          onChanged: (value) =>
                              textTools.setCodeDictation(value: value),
                        ),
                      ),
                      SettingsRow(
                        title: 'Fill-in templates',
                        subtitle: _countLine(
                          ruleCount(tools.templates),
                          'template',
                          'Say "template bug report" and fill it in by voice.',
                        ),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => _push(
                          context,
                          TemplatesPage(controller: textTools, pro: pro),
                        ),
                      ),
                      SettingsRow(
                        title: 'Per-app profiles',
                        subtitle: _countLine(
                          ruleCount(tools.profiles),
                          'profile',
                          'Different settings for different apps.',
                        ),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => _push(
                          context,
                          ProfilesPage(controller: textTools, pro: pro),
                        ),
                      ),
                    ],
                  ),
                  SettingsGroup(
                    label: 'Appearance',
                    children: [
                      Padding(
                        padding: const EdgeInsets.all(12),
                        child: _ThemePicker(
                          selected: values.theme,
                          onChanged: settings.setTheme,
                        ),
                      ),
                    ],
                  ),
                  SettingsGroup(
                    label: 'Privacy and data',
                    children: [
                      SettingsSwitchRow(
                        title: 'Send an anonymous usage ping',
                        subtitle:
                            'Once a day: the app version, the Android version '
                            'and a random id, so we can see how many people '
                            'use VoxScribe. Never audio or text.',
                        value: values.usagePing,
                        onChanged: (value) =>
                            settings.setUsagePing(value: value),
                      ),
                      if (openLink case final open?)
                        SettingsRow(
                          title: 'Privacy at a glance',
                          subtitle:
                              'What stays on your phone and every connection '
                              'the app makes.',
                          trailing: const Icon(Icons.open_in_new, size: 20),
                          onTap: () => open(_privacyUrl),
                        ),
                      SettingsRow(
                        title: 'Clear history',
                        subtitle:
                            'Removes every saved dictation and resets '
                            'your insights.',
                        titleColor: context.vox.red,
                        onTap: () => _confirmClear(context),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        );
      },
    );
  }

  String _setupSummary(SetupStatus status) {
    if (!status.permissionsComplete) {
      return '${status.doneCount} of ${SetupStep.values.length} done. Tap to '
          'finish.';
    }
    return status.bubbleRunning
        ? 'All set. The button is on.'
        : 'All set. The button is off.';
  }

  void _openSetup(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => SetupPage(controller: setup)),
    );
  }

  void _openPro(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => ProPage(pro: pro, snippets: snippets),
      ),
    );
  }

  void _push(BuildContext context, Widget page) {
    Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => page));
  }

  /// "3 replacements" when there are some, otherwise what the feature is for.
  String _countLine(int count, String noun, String empty) {
    if (count == 0) return empty;
    return '$count $noun${count == 1 ? '' : 's'}';
  }

  Future<void> _chooseLanguage(BuildContext context) async {
    final code = await pickLanguage(context, dictation.language);
    if (code != null) await dictation.chooseLanguage(code);
  }

  Future<void> _confirmClear(BuildContext context) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Clear history?'),
        content: const Text(
          'This removes every saved dictation and resets your insights. It '
          'cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: Text('Clear', style: TextStyle(color: context.vox.red)),
          ),
        ],
      ),
    );
    if (confirmed ?? false) await history.clear();
  }
}

class _Header extends StatelessWidget {
  const _Header();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 6),
      child: Row(
        children: [
          const BrandMark(),
          const SizedBox(width: 10),
          Text(
            'VoxScribe',
            style: Theme.of(context).textTheme.titleLarge
                ?.copyWith(fontSize: 19, letterSpacing: -0.2),
          ),
        ],
      ),
    );
  }
}

class _ThemePicker extends StatelessWidget {
  const _ThemePicker({required this.selected, required this.onChanged});

  final ThemeChoice selected;
  final ValueChanged<ThemeChoice> onChanged;

  static const _labels = {
    ThemeChoice.system: 'System',
    ThemeChoice.light: 'Light',
    ThemeChoice.dark: 'Dark',
  };

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    return SizedBox(
      width: double.infinity,
      child: SegmentedButton<ThemeChoice>(
        showSelectedIcon: false,
        segments: [
          for (final choice in ThemeChoice.values)
            ButtonSegment(value: choice, label: Text(_labels[choice]!)),
        ],
        selected: {selected},
        onSelectionChanged: (choices) => onChanged(choices.first),
        style: ButtonStyle(
          minimumSize: const WidgetStatePropertyAll(Size.fromHeight(48)),
          backgroundColor: WidgetStateProperty.resolveWith(
            (states) => states.contains(WidgetState.selected) ? c.accent : null,
          ),
          foregroundColor: WidgetStateProperty.resolveWith(
            (states) =>
                states.contains(WidgetState.selected) ? c.onAccent : c.text,
          ),
          side: WidgetStatePropertyAll(BorderSide(color: c.border)),
          textStyle: const WidgetStatePropertyAll(
            TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
          ),
        ),
      ),
    );
  }
}
