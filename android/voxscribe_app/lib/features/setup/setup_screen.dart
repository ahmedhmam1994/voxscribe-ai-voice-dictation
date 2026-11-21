import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/dictation/domain/dictation_language.dart';
import 'package:voxscribe_app/features/dictation/widgets/language_picker.dart';
import 'package:voxscribe_app/features/setup/domain/setup_status.dart';
import 'package:voxscribe_app/features/setup/setup_controller.dart';
import 'package:voxscribe_app/features/setup/widgets/how_it_works_demo.dart';
import 'package:voxscribe_app/features/setup/widgets/practice_card.dart';
import 'package:voxscribe_app/features/setup/widgets/restricted_steps.dart';
import 'package:voxscribe_app/features/setup/widgets/step_card.dart';
import 'package:voxscribe_app/shared/widgets/brand_mark.dart';

/// Guides the user through the permissions the floating button needs, then
/// turns the button on.
class SetupScreen extends StatefulWidget {
  const SetupScreen({required this.controller, this.onSkip, super.key});

  final SetupController controller;

  /// Shown as Skip for now under the main button, on a new install's first
  /// run, where this screen stands in for the Dictation screen.
  final VoidCallback? onSkip;

  @override
  State<SetupScreen> createState() => _SetupScreenState();
}

class _SetupScreenState extends State<SetupScreen> {
  late final AppLifecycleListener _lifecycle;

  @override
  void initState() {
    super.initState();
    // Coming back from a system screen or permission dialog.
    _lifecycle = AppLifecycleListener(onResume: widget.controller.refresh);
    widget.controller.refresh();
    widget.controller.opened();
  }

  @override
  void dispose() {
    _lifecycle.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: widget.controller,
      builder: (context, _) {
        final status = widget.controller.status;
        final appInfo = widget.controller.appInfoNext;
        return Column(
          children: [
            _Header(status: status),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
                children: [
                  _Intro(status: status),
                  _ModelStep(controller: widget.controller),
                  for (final step in SetupStep.values)
                    if (step != SetupStep.model)
                      StepCard(
                        title: _title(step),
                        state: _state(status, step),
                        description: status.nextStep == step
                            ? _description(step, status, appInfo: appInfo)
                            : null,
                        details: status.nextStep == step
                            ? _details(step, status, appInfo: appInfo)
                            : null,
                        highlighted: status.nextStep == step,
                        actionLabel: status.nextStep == step
                            ? _actionLabel(step, status, appInfo: appInfo)
                            : null,
                        onAction: appInfo
                            ? widget.controller.openAccessibilitySettings
                            : widget.controller.openAppInfo,
                      ),
                  if (status.permissionsComplete)
                    StepCard(
                      title: 'Floating button',
                      state: status.bubbleRunning
                          ? StepStatus.done
                          : StepStatus.todo,
                      description: status.bubbleRunning
                          ? 'On. Hold it to talk, release to type.'
                          : 'Off. Turn it on to dictate in any app.',
                      highlighted: !status.bubbleRunning,
                    ),
                  if (widget.controller.showPractice)
                    PracticeCard(onDone: widget.controller.hidePractice),
                  // Once the button can run, keep battery saving from stopping it.
                  if (status.permissionsComplete && !status.batteryUnrestricted)
                    _BatteryNotice(
                      xiaomi: status.xiaomi,
                      onAllow: widget.controller.requestBatteryExemption,
                      onAppInfo: widget.controller.openAppInfo,
                    ),
                  if (!status.notifications)
                    _NotificationNotice(
                      onOpen: widget.controller.openNotificationSettings,
                    ),
                  const _PrivacyNote(),
                ],
              ),
            ),
            if (widget.controller.errorMessage case final message?)
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 4, 20, 8),
                child: _ErrorText(message),
              ),
            // The practice box has its own Done and Skip.
            if (!widget.controller.showPractice)
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 10),
                child: _PrimaryButton(
                  label: _primaryLabel(status, appInfo: appInfo),
                  onPressed: widget.controller.busy
                      ? null
                      : widget.controller.performPrimaryAction,
                ),
              ),
            if (widget.onSkip case final skip?
                when !widget.controller.showPractice)
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: TextButton(
                  onPressed: skip,
                  child: Text(
                    'Skip for now',
                    style: TextStyle(color: context.vox.muted),
                  ),
                ),
              ),
          ],
        );
      },
    );
  }

  static String _title(SetupStep step) => switch (step) {
    SetupStep.model => 'Download the speech model',
    SetupStep.microphone => 'Allow the microphone',
    SetupStep.accessibility => 'Turn on VoxScribe in Accessibility',
    SetupStep.overlay => 'Allow display over other apps',
  };

  static String _description(
    SetupStep step,
    SetupStatus status, {
    required bool appInfo,
  }) => switch (step) {
    SetupStep.model => '',
    SetupStep.microphone =>
      'VoxScribe listens only while you hold the button. Your voice is '
          'transcribed on this phone.',
    SetupStep.accessibility when status.accessibilityNeedsRestart =>
      'It is switched on, but Android disconnected it, which can happen '
          'after an update. In the list, tap VoxScribe, turn it off, then on '
          'again.',
    SetupStep.accessibility when status.accessibilityRestricted =>
      'Android requires this to let an app type into other apps. It blocks '
          'the switch for apps installed from a file, so it may say '
          'Restricted setting. These taps get past it:',
    SetupStep.accessibility =>
      'Android requires this to let an app type into other apps. VoxScribe '
          'only watches which text box is focused, so it can put your '
          'dictation there. In the list, tap VoxScribe and turn it on.',
    SetupStep.overlay =>
      'This lets the small button float above your keyboard and other apps.',
  };

  /// The numbered taps past Android's Restricted setting block, with the one
  /// the user is on marked: the first, or App info after a try that failed.
  static Widget? _details(
    SetupStep step,
    SetupStatus status, {
    required bool appInfo,
  }) {
    if (step != SetupStep.accessibility ||
        !status.accessibilityRestricted ||
        status.accessibilityNeedsRestart) {
      return null;
    }
    return RestrictedSteps(current: appInfo ? 2 : 0);
  }

  /// The other half of the Restricted setting fix, whichever the primary
  /// button is not doing.
  static String? _actionLabel(
    SetupStep step,
    SetupStatus status, {
    required bool appInfo,
  }) {
    if (step != SetupStep.accessibility || !status.accessibilityRestricted) {
      return null;
    }
    return appInfo
        ? 'Open accessibility settings'
        : 'Already saw it? Open App info';
  }

  static StepStatus _state(SetupStatus status, SetupStep step) {
    if (status.isDone(step)) return StepStatus.done;
    return status.nextStep == step ? StepStatus.todo : StepStatus.waiting;
  }

  static String _primaryLabel(SetupStatus status, {required bool appInfo}) =>
      switch (status.nextStep) {
        SetupStep.model when status.modelError != null =>
          'Try the download again',
        SetupStep.model => 'Download (${status.modelMegabytes} MB)',
        SetupStep.microphone => 'Allow microphone',
        SetupStep.accessibility when appInfo => 'Open App info',
        SetupStep.accessibility => 'Open accessibility settings',
        SetupStep.overlay => 'Allow display over other apps',
        null =>
          status.bubbleRunning
              ? 'Turn off floating button'
              : 'Show floating button',
      };
}

/// The first step: the speech model for the language the user speaks. Its
/// download runs in the background, so the steps after it can be done
/// meanwhile, and this card shows the progress.
class _ModelStep extends StatelessWidget {
  const _ModelStep({required this.controller});

  final SetupController controller;

  @override
  Widget build(BuildContext context) {
    final status = controller.status;
    final language = languageForCode(status.language).name;
    final current = status.nextStep == SetupStep.model;
    final StepStatus state;
    final String? description;
    Widget? details;
    String? actionLabel;
    VoidCallback? onAction;
    if (status.modelInstalled) {
      state = StepStatus.done;
      description = 'Ready for $language.';
      actionLabel = 'Speak another language?';
      onAction = () => _pick(context);
    } else if (status.modelDownloading) {
      state = StepStatus.working;
      description =
          '${status.modelPercent}% of ${status.modelMegabytes} MB. Do the '
          'next steps meanwhile; VoxScribe types once this finishes.';
      details = ClipRRect(
        borderRadius: BorderRadius.circular(999),
        child: LinearProgressIndicator(
          minHeight: 6,
          color: context.vox.accent,
          backgroundColor: context.vox.border,
          value: status.modelPercent <= 0 ? null : status.modelPercent / 100,
        ),
      );
      actionLabel = 'Cancel download';
      onAction = controller.cancelModelDownload;
    } else {
      state = current ? StepStatus.todo : StepStatus.waiting;
      final error = status.modelError;
      description = error != null && error != 'Cancelled.'
          ? 'The download stopped: $error'
          : 'VoxScribe types $language with a speech model that runs on '
                'this phone, so nothing you say is uploaded. It downloads '
                'once (${status.modelMegabytes} MB, so use Wi-Fi), then '
                'works offline.';
      actionLabel = 'Not $language? Change the language';
      onAction = () => _pick(context);
    }
    return StepCard(
      title: status.modelInstalled
          ? 'Speech model'
          : 'Download the speech model',
      state: state,
      description: description,
      details: details,
      highlighted: current,
      actionLabel: controller.busy ? null : actionLabel,
      onAction: onAction,
    );
  }

  Future<void> _pick(BuildContext context) async {
    final code = await pickLanguage(context, controller.status.language);
    if (code != null) await controller.chooseLanguage(code);
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.status});

  final SetupStatus status;

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
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
          const Spacer(),
          if (!status.permissionsComplete)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: c.card,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: c.border),
              ),
              child: Text(
                '${status.doneCount} of ${SetupStep.values.length} done',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
        ],
      ),
    );
  }
}

class _Intro extends StatelessWidget {
  const _Intro({required this.status});

  final SetupStatus status;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context).textTheme;
    final ready = status.permissionsComplete;
    return Padding(
      padding: const EdgeInsets.only(top: 10, bottom: 18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            ready ? 'You are set' : 'A few quick steps',
            style: theme.titleLarge,
          ),
          const SizedBox(height: 6),
          Text(
            ready
                ? 'Turn on the floating button and hold it over any app. Your '
                      'own keyboard stays exactly as it is.'
                : 'Then hold the floating button over any app. Your own '
                      'keyboard stays exactly as it is.',
            style: theme.bodyMedium?.copyWith(
              color: context.vox.muted,
              fontSize: 15,
            ),
          ),
          const SizedBox(height: 14),
          const HowItWorksDemo(),
        ],
      ),
    );
  }
}

class _ErrorText extends StatelessWidget {
  const _ErrorText(this.message);

  final String message;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Text(
        message,
        style: Theme.of(context).textTheme.bodyMedium
            ?.copyWith(color: context.vox.red),
      ),
    );
  }
}

/// Notifications are not required, but two things depend on them: the button
/// that brings the floating button back after a pause, and the warning that
/// the typing service disconnected.
class _NotificationNotice extends StatelessWidget {
  const _NotificationNotice({required this.onOpen});

  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    return Container(
      margin: const EdgeInsets.only(top: 6, bottom: 14),
      padding: const EdgeInsets.fromLTRB(16, 14, 8, 8),
      decoration: BoxDecoration(
        color: c.card,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: c.amber.withValues(alpha: 0.5)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.notifications_off_outlined, color: c.amber, size: 22),
              const SizedBox(width: 10),
              Text(
                'Notifications are off',
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            'The floating button still works. Notifications are how you bring '
            'it back after hiding it, and how VoxScribe tells you if Android '
            'disconnects it.',
            style: Theme.of(context).textTheme.bodyMedium
                ?.copyWith(color: c.muted),
          ),
          Align(
            alignment: Alignment.centerRight,
            child: TextButton(
              onPressed: onOpen,
              child: Text(
                'Open notification settings',
                style: TextStyle(color: c.accentInk),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Some phones stop apps in the background to save battery, and the floating
/// button then disappears until VoxScribe is opened again.
class _BatteryNotice extends StatelessWidget {
  const _BatteryNotice({
    required this.xiaomi,
    required this.onAllow,
    required this.onAppInfo,
  });

  final bool xiaomi;
  final VoidCallback onAllow;
  final VoidCallback onAppInfo;

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    final body = Theme.of(context).textTheme.bodyMedium
        ?.copyWith(color: c.muted);
    return Container(
      margin: const EdgeInsets.only(top: 6, bottom: 14),
      padding: const EdgeInsets.fromLTRB(16, 14, 8, 8),
      decoration: BoxDecoration(
        color: c.card,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: c.amber.withValues(alpha: 0.5)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.battery_alert_outlined, color: c.amber, size: 22),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  'Keep the button from disappearing',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            'Battery saving can close the floating button in the background. '
            'Allow VoxScribe to run so the button stays ready. It only uses '
            'the microphone while you dictate.',
            style: body,
          ),
          if (xiaomi) ...[
            const SizedBox(height: 8),
            Text(
              'On Xiaomi phones, also open App info, tap Battery saver and '
              'choose No restrictions.',
              style: body,
            ),
          ],
          Align(
            alignment: Alignment.centerRight,
            child: Wrap(
              alignment: WrapAlignment.end,
              children: [
                if (xiaomi)
                  TextButton(
                    onPressed: onAppInfo,
                    child: Text(
                      'Open App info',
                      style: TextStyle(color: c.accentInk),
                    ),
                  ),
                TextButton(
                  onPressed: onAllow,
                  child: Text('Allow', style: TextStyle(color: c.accentInk)),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _PrivacyNote extends StatelessWidget {
  const _PrivacyNote();

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.lock_outline, size: 18, color: c.accentInk),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              'Your voice is transcribed on this phone. It is never uploaded, '
              'and the model works in airplane mode.',
              style: Theme.of(context).textTheme.bodyMedium
                  ?.copyWith(color: c.muted),
            ),
          ),
        ],
      ),
    );
  }
}

class _PrimaryButton extends StatelessWidget {
  const _PrimaryButton({required this.label, required this.onPressed});

  final String label;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    return SizedBox(
      width: double.infinity,
      height: 60,
      child: FilledButton(
        onPressed: onPressed,
        style: FilledButton.styleFrom(
          backgroundColor: c.accent,
          foregroundColor: c.onAccent,
          disabledBackgroundColor: c.accent.withValues(alpha: 0.5),
          disabledForegroundColor: c.onAccent,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          textStyle: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700),
        ),
        child: Text(label),
      ),
    );
  }
}
