import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/dictation/dictation_controller.dart';
import 'package:voxscribe_app/features/dictation/domain/dictation_language.dart';
import 'package:voxscribe_app/features/dictation/widgets/language_picker.dart';
import 'package:voxscribe_app/features/history/history_controller.dart';
import 'package:voxscribe_app/features/settings/domain/app_settings.dart';
import 'package:voxscribe_app/features/settings/settings_controller.dart';
import 'package:voxscribe_app/features/settings/widgets/settings_group.dart';
import 'package:voxscribe_app/features/setup/domain/setup_status.dart';
import 'package:voxscribe_app/features/setup/setup_controller.dart';
import 'package:voxscribe_app/features/setup/setup_page.dart';
import 'package:voxscribe_app/shared/widgets/brand_mark.dart';

/// Language, cleanup, theme, the setup page and clearing history.
class SettingsScreen extends StatelessWidget {
  const SettingsScreen({
    required this.settings,
    required this.setup,
    required this.dictation,
    required this.history,
    super.key,
  });

  final SettingsController settings;
  final SetupController setup;
  final DictationController dictation;
  final HistoryController history;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: Listenable.merge([settings, setup, dictation]),
      builder: (context, _) {
        final values = settings.settings;
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
                    label: 'Your data',
                    children: [
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
