import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/history/history_controller.dart';
import 'package:voxscribe_app/features/insights/domain/insights.dart';
import 'package:voxscribe_app/features/insights/widgets/week_bars.dart';
import 'package:voxscribe_app/shared/widgets/brand_mark.dart';
import 'package:voxscribe_app/shared/widgets/section_label.dart';
import 'package:voxscribe_app/shared/widgets/vox_card.dart';

/// Totals, pace and streak worked out from the saved dictations.
class InsightsScreen extends StatelessWidget {
  const InsightsScreen({
    required this.history,
    this.clock = DateTime.now,
    super.key,
  });

  final HistoryController history;

  /// The current time. Replaced in tests.
  final DateTime Function() clock;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: history,
      builder: (context, _) {
        final now = clock();
        final insights = Insights.from(history.entries, now: now);
        return Column(
          children: [
            const _Header(),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 20),
                children: [
                  Text(
                    'Insights',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Counted on this phone only. Nothing leaves it.',
                    style: Theme.of(context).textTheme.bodyMedium
                        ?.copyWith(color: context.vox.muted),
                  ),
                  const SizedBox(height: 18),
                  if (insights.isEmpty)
                    const _EmptyState()
                  else
                    ..._content(context, insights, now),
                ],
              ),
            ),
          ],
        );
      },
    );
  }

  List<Widget> _content(BuildContext context, Insights insights, DateTime now) {
    final theme = Theme.of(context).textTheme;
    final c = context.vox;
    final longest = insights.longest;
    return [
      VoxCard(
        padding: const EdgeInsets.all(18),
        child: _Stat(
          value: _thousands(insights.totalWords),
          caption: 'words dictated, all time',
          valueStyle: theme.displayMedium,
        ),
      ),
      const SizedBox(height: 10),
      Row(
        children: [
          Expanded(
            child: VoxCard(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              child: _Stat(
                value: insights.wordsPerMinute == 0
                    ? '-'
                    : '${insights.wordsPerMinute}',
                caption: 'words per minute',
                valueStyle: _smallStat(theme),
              ),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: VoxCard(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              child: _Stat(
                value: insights.streakDays == 1
                    ? '1 day'
                    : '${insights.streakDays} days',
                caption: 'current streak',
                valueStyle: _smallStat(theme),
              ),
            ),
          ),
        ],
      ),
      const SectionLabel('This week'),
      VoxCard(
        padding: const EdgeInsets.fromLTRB(12, 16, 12, 12),
        child: WeekBars(wordsPerDay: insights.wordsPerDay, today: now),
      ),
      if (longest != null) ...[
        const SectionLabel('Longest dictation'),
        VoxCard(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          child: Text.rich(
            TextSpan(
              children: [
                TextSpan(
                  text: '${longest.wordCount} words',
                  style: theme.bodyMedium,
                ),
                TextSpan(
                  text: ', ${longest.duration.inSeconds} s',
                  style: theme.bodyMedium?.copyWith(color: c.muted),
                ),
              ],
            ),
          ),
        ),
      ],
    ];
  }

  TextStyle? _smallStat(TextTheme theme) {
    return theme.titleLarge?.copyWith(
      letterSpacing: -0.3,
      fontFeatures: const [FontFeature.tabularFigures()],
    );
  }

  /// 12480 becomes "12,480".
  String _thousands(int value) {
    final digits = value.toString();
    final buffer = StringBuffer();
    for (var i = 0; i < digits.length; i++) {
      if (i > 0 && (digits.length - i) % 3 == 0) buffer.write(',');
      buffer.write(digits[i]);
    }
    return buffer.toString();
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

class _Stat extends StatelessWidget {
  const _Stat({
    required this.value,
    required this.caption,
    required this.valueStyle,
  });

  final String value;
  final String caption;
  final TextStyle? valueStyle;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(value, style: valueStyle),
        const SizedBox(height: 4),
        Text(caption, style: Theme.of(context).textTheme.bodySmall),
      ],
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return VoxCard(
      child: Text(
        'Nothing to count yet. Dictate something, here or with the floating '
        'button, and your numbers show up.',
        style: Theme.of(context).textTheme.bodyLarge
            ?.copyWith(color: context.vox.muted),
      ),
    );
  }
}
