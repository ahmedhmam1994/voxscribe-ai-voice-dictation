import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/core/dates.dart';

/// Words per day for the last week as columns of small blocks, one block per
/// [unit] words, with today in full green. The blocks drop into place day by
/// day when the chart first shows, and again when the numbers change.
class WeekBars extends StatefulWidget {
  const WeekBars({required this.wordsPerDay, required this.today, super.key});

  /// Oldest day first; the last item is [today].
  final List<int> wordsPerDay;
  final DateTime today;

  /// The tallest column holds this many blocks.
  static const maxBlocks = 12;

  /// How many words one block stands for: the smallest of 10, 25, 50 and 100
  /// that fits the busiest day, so a quiet week still fills the chart, or more
  /// than 100 in a big week.
  static int unitFor(List<int> wordsPerDay) {
    final peak = wordsPerDay.fold<int>(0, (a, b) => a > b ? a : b);
    for (final unit in const [10, 25, 50, 100]) {
      if (peak <= unit * maxBlocks) return unit;
    }
    return ((peak / maxBlocks) / 100).ceil() * 100;
  }

  /// How many blocks a day with [words] gets. Any dictation shows at least one.
  static int blocksFor(int words, int unit) =>
      words == 0 ? 0 : (words / unit).round().clamp(1, maxBlocks);

  @override
  State<WeekBars> createState() => _WeekBarsState();
}

class _WeekBarsState extends State<WeekBars>
    with SingleTickerProviderStateMixin {
  static const double _block = 10;
  static const double _gap = 3;
  static const _initials = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];

  late final AnimationController _drop = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1400),
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_drop.isAnimating || _drop.isCompleted) return;
    _play();
  }

  @override
  void didUpdateWidget(WeekBars oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!_same(oldWidget.wordsPerDay, widget.wordsPerDay)) _play();
  }

  void _play() {
    if (MediaQuery.disableAnimationsOf(context)) {
      _drop.value = 1;
    } else {
      _drop.forward(from: 0);
    }
  }

  static bool _same(List<int> a, List<int> b) {
    if (a.length != b.length) return false;
    for (var i = 0; i < a.length; i++) {
      if (a[i] != b[i]) return false;
    }
    return true;
  }

  @override
  void dispose() {
    _drop.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    final days = widget.wordsPerDay;
    final unit = WeekBars.unitFor(days);
    const height = WeekBars.maxBlocks * (_block + _gap);
    return Semantics(
      label: 'Words per day this week',
      child: Column(
        children: [
          SizedBox(
            height: height,
            child: AnimatedBuilder(
              animation: _drop,
              builder: (context, _) => Row(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  for (var i = 0; i < days.length; i++)
                    Expanded(
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 4),
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.end,
                          children: [
                            for (
                              var j = WeekBars.blocksFor(days[i], unit) - 1;
                              j >= 0;
                              j--
                            )
                              _blockAt(
                                c,
                                day: i,
                                level: j,
                                today: i == days.length - 1,
                              ),
                          ],
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              for (var i = 0; i < days.length; i++)
                Expanded(
                  child: Text(
                    _initial(i),
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: i == days.length - 1 ? c.accentInk : c.muted,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            'Each block is $unit words',
            style: Theme.of(context).textTheme.bodySmall
                ?.copyWith(fontSize: 12),
          ),
        ],
      ),
    );
  }

  /// One block, falling in after the days before it and the blocks below it.
  Widget _blockAt(
    VoxColors c, {
    required int day,
    required int level,
    required bool today,
  }) {
    final start = (day * 0.08 + level * 0.025).clamp(0.0, 0.7);
    final t = Interval(
      start,
      start + 0.3,
      curve: Curves.easeOutCubic,
    ).transform(_drop.value);
    return Opacity(
      opacity: t,
      child: Transform.translate(
        offset: Offset(0, -36 * (1 - t)),
        child: Container(
          height: _block,
          margin: const EdgeInsets.only(top: _gap),
          decoration: BoxDecoration(
            color: today ? c.accent : c.accent.withValues(alpha: 0.28),
            borderRadius: BorderRadius.circular(3),
          ),
        ),
      ),
    );
  }

  /// The weekday initial for the day at [index] in the list.
  String _initial(int index) {
    final daysBack = widget.wordsPerDay.length - 1 - index;
    final day = daysBefore(widget.today, daysBack);
    return _initials[day.weekday - 1];
  }
}
