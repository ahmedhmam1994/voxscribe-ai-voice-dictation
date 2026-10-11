import 'package:flutter/foundation.dart';
import 'package:voxscribe_app/core/dates.dart';
import 'package:voxscribe_app/features/history/domain/dictation_entry.dart';

/// Numbers worked out from the saved dictations.
@immutable
class Insights {
  const Insights({
    required this.totalWords,
    required this.wordsPerMinute,
    required this.streakDays,
    required this.wordsPerDay,
    required this.longest,
  });

  /// How many days the week chart covers, ending today.
  static const weekLength = 7;

  /// Every word dictated, all time.
  final int totalWords;

  /// Speaking pace across all dictations, or 0 when no durations are known.
  final int wordsPerMinute;

  /// Consecutive days with a dictation. A streak that ended yesterday still
  /// counts, so it only breaks after a whole day without dictating.
  final int streakDays;

  /// Words per day for the last [weekLength] days, oldest first, so the last
  /// item is today.
  final List<int> wordsPerDay;

  /// The longest single dictation, or null when there are none.
  final DictationEntry? longest;

  bool get isEmpty => totalWords == 0;

  factory Insights.from(List<DictationEntry> entries, {required DateTime now}) {
    final wordsByDay = <DateTime, int>{};
    var totalWords = 0;
    var timedWords = 0;
    var timedMilliseconds = 0;
    DictationEntry? longest;

    for (final entry in entries) {
      final words = entry.wordCount;
      totalWords += words;
      final day = dateOnly(entry.createdAt);
      wordsByDay[day] = (wordsByDay[day] ?? 0) + words;
      if (entry.duration > Duration.zero) {
        timedWords += words;
        timedMilliseconds += entry.duration.inMilliseconds;
      }
      if (longest == null || words > longest.wordCount) longest = entry;
    }

    final today = dateOnly(now);
    return Insights(
      totalWords: totalWords,
      wordsPerMinute: timedMilliseconds == 0
          ? 0
          : (timedWords / (timedMilliseconds / 60000)).round(),
      streakDays: _streak(wordsByDay.keys.toSet(), today),
      wordsPerDay: [
        for (var back = weekLength - 1; back >= 0; back--)
          wordsByDay[daysBefore(today, back)] ?? 0,
      ],
      longest: longest,
    );
  }

  static int _streak(Set<DateTime> days, DateTime today) {
    var cursor = days.contains(today) ? today : daysBefore(today, 1);
    var streak = 0;
    while (days.contains(cursor)) {
      streak++;
      cursor = DateTime(cursor.year, cursor.month, cursor.day - 1);
    }
    return streak;
  }
}
