import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/setup/domain/setup_status.dart';
import 'package:voxscribe_app/features/setup/setup_controller.dart';
import 'package:voxscribe_app/features/setup/setup_page.dart';

/// Points new users from the Dictation screen to the floating button, which
/// is how VoxScribe types into other apps. Without it they only ever dictate
/// inside VoxScribe. Shows until setup is finished and the button is on.
class SetupReminderCard extends StatelessWidget {
  const SetupReminderCard({required this.controller, super.key});

  final SetupController controller;

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    final theme = Theme.of(context).textTheme;
    final status = controller.status;
    final stepsLeft = !status.permissionsComplete;
    // Everything else is done (an update from a version with a built-in
    // model, for one): only the speech model is missing.
    final onlyModel =
        status.nextStep == SetupStep.model &&
        SetupStep.values.every((s) => s == SetupStep.model || status.isDone(s));
    if (status.modelDownloading) return _Downloading(controller: controller);
    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      padding: const EdgeInsets.fromLTRB(16, 14, 12, 10),
      decoration: BoxDecoration(
        color: c.card,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: c.accent.withValues(alpha: 0.6)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.bubble_chart_outlined, color: c.accentInk, size: 22),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  onlyModel
                      ? 'Download the speech model'
                      : stepsLeft
                      ? 'Dictate in any app'
                      : 'Turn on the floating button',
                  style: theme.titleMedium,
                ),
              ),
              if (stepsLeft && !onlyModel)
                Text(
                  '${status.doneCount} of ${SetupStep.values.length} done',
                  style: theme.bodySmall,
                ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            onlyModel
                ? 'VoxScribe now types with a far more accurate speech model '
                      'that runs on this phone. It downloads once '
                      '(${status.modelMegabytes} MB, so use Wi-Fi). Until then '
                      'the floating button cannot type.'
                : stepsLeft
                ? 'A few quick steps turn on the floating button, so you can '
                      'talk into your chats, email and browser with your own '
                      'keyboard.'
                : 'Setup is done. Turn the button on to dictate in any app.',
            style: theme.bodyMedium?.copyWith(color: c.muted),
          ),
          const SizedBox(height: 4),
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              TextButton(
                onPressed: controller.hideReminder,
                child: Text('Not now', style: TextStyle(color: c.muted)),
              ),
              const SizedBox(width: 4),
              FilledButton(
                onPressed: controller.busy
                    ? null
                    : onlyModel
                    ? controller.performPrimaryAction
                    : stepsLeft
                    ? () => _openSetup(context)
                    : controller.performPrimaryAction,
                style: FilledButton.styleFrom(
                  backgroundColor: c.accent,
                  foregroundColor: c.onAccent,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: Text(
                  onlyModel
                      ? 'Download'
                      : stepsLeft
                      ? 'Set up'
                      : 'Turn on',
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  void _openSetup(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => SetupPage(controller: controller),
      ),
    );
  }
}

/// The speech model is downloading: how far it is, so the wait is not a mystery.
class _Downloading extends StatelessWidget {
  const _Downloading({required this.controller});

  final SetupController controller;

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    final theme = Theme.of(context).textTheme;
    final status = controller.status;
    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      padding: const EdgeInsets.fromLTRB(16, 14, 12, 10),
      decoration: BoxDecoration(
        color: c.card,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: c.accent.withValues(alpha: 0.6)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.download_outlined, color: c.accentInk, size: 22),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  'Downloading the speech model',
                  style: theme.titleMedium,
                ),
              ),
              Text('${status.modelPercent}%', style: theme.bodySmall),
            ],
          ),
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              minHeight: 6,
              color: c.accent,
              backgroundColor: c.border,
              value: status.modelPercent <= 0
                  ? null
                  : status.modelPercent / 100,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '${status.modelMegabytes} MB, once. VoxScribe types as soon as it '
            'finishes, and works offline from then on.',
            style: theme.bodyMedium?.copyWith(color: c.muted),
          ),
          Align(
            alignment: Alignment.centerRight,
            child: TextButton(
              onPressed: controller.hideReminder,
              child: Text('Hide', style: TextStyle(color: c.muted)),
            ),
          ),
        ],
      ),
    );
  }
}
