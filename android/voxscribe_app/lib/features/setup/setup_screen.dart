import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/setup/domain/setup_status.dart';
import 'package:voxscribe_app/features/setup/setup_controller.dart';
import 'package:voxscribe_app/features/setup/widgets/step_card.dart';
import 'package:voxscribe_app/shared/widgets/brand_mark.dart';

/// Guides the user through the permissions the floating button needs, then
/// turns the button on.
class SetupScreen extends StatefulWidget {
  const SetupScreen({required this.controller, super.key});

  final SetupController controller;

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
        return Column(
          children: [
            _Header(status: status),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
                children: [
                  _Intro(status: status),
                  for (final step in SetupStep.values)
                    StepCard(
                      title: _title(step),
                      state: _state(status, step),
                      description: status.nextStep == step
                          ? _description(step)
                          : null,
                      highlighted: status.nextStep == step,
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
                  const _PrivacyNote(),
                ],
              ),
            ),
            if (widget.controller.errorMessage case final message?)
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 4, 20, 8),
                child: _ErrorText(message),
              ),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 10),
              child: _PrimaryButton(
                label: _primaryLabel(status),
                onPressed: widget.controller.busy
                    ? null
                    : widget.controller.performPrimaryAction,
              ),
            ),
          ],
        );
      },
    );
  }

  static String _title(SetupStep step) => switch (step) {
    SetupStep.microphone => 'Allow the microphone',
    SetupStep.accessibility => 'Turn on VoxScribe in Accessibility',
    SetupStep.overlay => 'Allow display over other apps',
  };

  static String _description(SetupStep step) => switch (step) {
    SetupStep.microphone =>
      'VoxScribe listens only while you hold the button. Your voice is '
          'transcribed on this phone.',
    SetupStep.accessibility =>
      'Android requires this to let an app type into other apps. VoxScribe '
          'only watches which text box is focused, so it can put your '
          'dictation there. In the list, tap VoxScribe and turn it on.',
    SetupStep.overlay =>
      'This lets the small button float above your keyboard and other apps.',
  };

  static StepStatus _state(SetupStatus status, SetupStep step) {
    if (status.isDone(step)) return StepStatus.done;
    return status.nextStep == step ? StepStatus.todo : StepStatus.waiting;
  }

  static String _primaryLabel(SetupStatus status) => switch (status.nextStep) {
    SetupStep.microphone => 'Allow microphone',
    SetupStep.accessibility => 'Open accessibility settings',
    SetupStep.overlay => 'Allow display over other apps',
    null =>
      status.bubbleRunning
          ? 'Turn off floating button'
          : 'Show floating button',
  };
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
            ready ? 'You are set' : 'Three quick steps',
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
