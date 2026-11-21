import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';

/// The taps that get past Android's "Restricted setting" block on the
/// Accessibility switch, as a numbered list with the current one marked.
class RestrictedSteps extends StatelessWidget {
  const RestrictedSteps({required this.current, super.key});

  /// Index into [steps] of the tap the user is on.
  final int current;

  static const steps = [
    'Tap Open accessibility settings. Find VoxScribe (it can be under '
        'Downloaded apps or Installed apps) and tap it.',
    'If Android says Restricted setting, tap OK and come back here.',
    'Tap Open App info, then the three dots at the top right, then Allow '
        'restricted settings.',
    'Come back, tap Open accessibility settings again and turn VoxScribe on.',
  ];

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    final theme = Theme.of(context).textTheme;
    return Column(
      children: [
        for (var i = 0; i < steps.length; i++)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 24,
                  height: 24,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: i == current
                        ? c.accent
                        : c.muted.withValues(alpha: 0.18),
                  ),
                  child: Text(
                    '${i + 1}',
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w700,
                      color: i == current ? c.onAccent : c.muted,
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    steps[i],
                    style: theme.bodyMedium?.copyWith(
                      color: i == current ? c.text : c.muted,
                      fontWeight: i == current ? FontWeight.w600 : null,
                      height: 1.35,
                    ),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}
