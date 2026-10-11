import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/features/history/domain/dictation_entry.dart';
import 'package:voxscribe_app/features/insights/domain/insights.dart';

/// Today for every test: Saturday 10 October 2026, mid afternoon.
final _now = DateTime(2026, 10, 10, 15);

DictationEntry _entry(
  int daysAgo,
  String text, {
  Duration duration = const Duration(seconds: 6),
}) {
  return DictationEntry(
    text: text,
    createdAt: DateTime(2026, 10, 10 - daysAgo, 12),
    duration: duration,
  );
}

void main() {
  test('no dictations means empty insights', () {
    final insights = Insights.from(const [], now: _now);

    expect(insights.isEmpty, isTrue);
    expect(insights.totalWords, 0);
    expect(insights.streakDays, 0);
    expect(insights.longest, isNull);
    expect(insights.wordsPerDay, List.filled(7, 0));
  });

  test('adds up every word', () {
    final insights = Insights.from([
      _entry(0, 'one two three'),
      _entry(1, 'four five'),
    ], now: _now);

    expect(insights.totalWords, 5);
    expect(insights.isEmpty, isFalse);
  });

  test('works out the speaking pace from the timed dictations', () {
    // 20 words in 10 seconds is 120 words per minute.
    final insights = Insights.from([
      _entry(
        0,
        List.filled(20, 'word').join(' '),
        duration: const Duration(seconds: 10),
      ),
    ], now: _now);

    expect(insights.wordsPerMinute, 120);
  });

  test('ignores dictations with no known duration for the pace', () {
    final insights = Insights.from([
      _entry(
        0,
        List.filled(20, 'word').join(' '),
        duration: const Duration(seconds: 10),
      ),
      _entry(1, List.filled(500, 'word').join(' '), duration: Duration.zero),
    ], now: _now);

    expect(insights.wordsPerMinute, 120);
    expect(insights.totalWords, 520);
  });

  test('the pace is zero when no duration is known', () {
    final insights = Insights.from([
      _entry(0, 'a b c', duration: Duration.zero),
    ], now: _now);

    expect(insights.wordsPerMinute, 0);
  });

  group('streak', () {
    test('counts consecutive days ending today', () {
      final insights = Insights.from([
        _entry(0, 'a'),
        _entry(1, 'b'),
        _entry(2, 'c'),
      ], now: _now);

      expect(insights.streakDays, 3);
    });

    test('a streak that ended yesterday still counts', () {
      final insights = Insights.from([
        _entry(1, 'a'),
        _entry(2, 'b'),
      ], now: _now);

      expect(insights.streakDays, 2);
    });

    test('breaks after a whole day without dictating', () {
      final insights = Insights.from([
        _entry(2, 'a'),
        _entry(3, 'b'),
      ], now: _now);

      expect(insights.streakDays, 0);
    });

    test('a gap ends the streak', () {
      final insights = Insights.from([
        _entry(0, 'a'),
        _entry(1, 'b'),
        _entry(3, 'c'),
      ], now: _now);

      expect(insights.streakDays, 2);
    });

    test('several dictations on one day count once', () {
      final insights = Insights.from([
        _entry(0, 'a'),
        _entry(0, 'b'),
      ], now: _now);

      expect(insights.streakDays, 1);
    });
  });

  test('the week chart covers seven days ending today', () {
    final insights = Insights.from([
      _entry(0, 'one two'),
      _entry(0, 'three'),
      _entry(2, 'four five six four'),
      _entry(6, 'seven'),
      _entry(7, 'too old to show'),
    ], now: _now);

    expect(insights.wordsPerDay, [1, 0, 0, 0, 4, 0, 3]);
  });

  test('picks the longest dictation', () {
    final insights = Insights.from([
      _entry(0, 'short one'),
      _entry(1, 'a much longer dictation than the other'),
      _entry(2, 'medium length here'),
    ], now: _now);

    expect(insights.longest?.text, 'a much longer dictation than the other');
  });
}
