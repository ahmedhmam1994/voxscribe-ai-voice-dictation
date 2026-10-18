import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/core/dates.dart';

/// Words per day for the last week, with today highlighted. The bars grow up
/// from the baseline when the chart first shows (one after another, left to
/// right) and glide to new heights when the numbers change.
class WeekBars extends StatelessWidget {
  const WeekBars({required this.wordsPerDay, required this.today, super.key});

  static const double _chartHeight = 120;
  static const double _minBar = 6;
  static const _initials = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];

  /// Oldest day first; the last item is [today].
  final List<int> wordsPerDay;
  final DateTime today;

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    final still = MediaQuery.disableAnimationsOf(context);
    final peak = wordsPerDay.fold<int>(0, (a, b) => a > b ? a : b);
    return Semantics(
      label: 'Words per day this week',
      child: Column(
        children: [
          SizedBox(
            height: _chartHeight,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                for (var i = 0; i < wordsPerDay.length; i++)
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 5),
                      child: TweenAnimationBuilder<double>(
                        tween: Tween(
                          begin: _minBar,
                          end: _barHeight(wordsPerDay[i], peak),
                        ),
                        duration: still
                            ? Duration.zero
                            : Duration(milliseconds: 450 + 50 * i),
                        curve: Curves.easeOutCubic,
                        builder: (context, height, _) => Container(
                          height: height,
                          decoration: BoxDecoration(
                            color: i == wordsPerDay.length - 1
                                ? c.accentInk
                                : c.raised,
                            borderRadius: const BorderRadius.vertical(
                              top: Radius.circular(6),
                              bottom: Radius.circular(3),
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              for (var i = 0; i < wordsPerDay.length; i++)
                Expanded(
                  child: Text(
                    _initial(i),
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: i == wordsPerDay.length - 1 ? c.text : c.muted,
                    ),
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }

  double _barHeight(int words, int peak) {
    if (peak == 0) return _minBar;
    return _minBar + (_chartHeight - _minBar) * words / peak;
  }

  /// The weekday initial for the day at [index] in the list.
  String _initial(int index) {
    final daysBack = wordsPerDay.length - 1 - index;
    final day = daysBefore(today, daysBack);
    return _initials[day.weekday - 1];
  }
}
