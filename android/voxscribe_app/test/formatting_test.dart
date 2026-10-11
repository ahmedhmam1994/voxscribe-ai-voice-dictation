import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/core/formatting.dart';

void main() {
  group('formatClock', () {
    test(
      'morning',
      () => expect(formatClock(DateTime(2026, 1, 1, 9, 5)), '9:05 AM'),
    );
    test(
      'midnight',
      () => expect(formatClock(DateTime(2026, 1, 1, 0, 30)), '12:30 AM'),
    );
    test(
      'noon',
      () => expect(formatClock(DateTime(2026, 1, 1, 12, 0)), '12:00 PM'),
    );
    test(
      'evening',
      () => expect(formatClock(DateTime(2026, 1, 1, 18, 47)), '6:47 PM'),
    );
  });

  test('formatSeconds keeps one decimal', () {
    expect(formatSeconds(const Duration(milliseconds: 2400)), '2.4 s');
  });

  test('formatWordCount handles one and many', () {
    expect(formatWordCount(1), '1 word');
    expect(formatWordCount(12), '12 words');
  });
}
