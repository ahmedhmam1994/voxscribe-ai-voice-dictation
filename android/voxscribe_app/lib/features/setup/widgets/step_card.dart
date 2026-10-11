import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/shared/widgets/vox_card.dart';

/// Where a setup step stands.
enum StepStatus { done, todo, waiting }

/// One setup step: a title, its state, and an explanation while it is current.
class StepCard extends StatelessWidget {
  const StepCard({
    required this.title,
    required this.state,
    this.description,
    this.highlighted = false,
    super.key,
  });

  final String title;
  final StepStatus state;

  /// Shown under the title. Pass it only for the step being worked on.
  final String? description;
  final bool highlighted;

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    final theme = Theme.of(context).textTheme;
    final text = description;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(14),
          border: highlighted
              ? Border.all(color: c.accentInk.withValues(alpha: 0.55))
              : null,
        ),
        child: VoxCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      title,
                      style: theme.bodyLarge?.copyWith(
                        fontWeight: FontWeight.w700,
                        color: state == StepStatus.waiting ? c.muted : c.text,
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  _StateChip(state: state),
                ],
              ),
              if (text != null) ...[
                const SizedBox(height: 6),
                Text(text, style: theme.bodyMedium?.copyWith(color: c.muted)),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _StateChip extends StatelessWidget {
  const _StateChip({required this.state});

  final StepStatus state;

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    final (label, color) = switch (state) {
      StepStatus.done => ('Done', c.accentInk),
      StepStatus.todo => ('To do', c.amber),
      StepStatus.waiting => ('Next', c.muted),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label.toUpperCase(),
        style: TextStyle(
          color: color,
          fontSize: 12,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.6,
        ),
      ),
    );
  }
}
