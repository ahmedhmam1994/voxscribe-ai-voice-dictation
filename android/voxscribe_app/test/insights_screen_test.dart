import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/features/history/domain/dictation_entry.dart';

import 'support/fake_history_repository.dart';
import 'support/test_app.dart';

void main() {
  testWidgets('shows a friendly message before any dictation', (tester) async {
    await tester.pumpWidget(buildTestApp());
    await openTab(tester, 'Insights');

    expect(find.textContaining('Nothing to count yet'), findsOneWidget);
    expect(find.text('words dictated, all time'), findsNothing);
  });

  testWidgets('shows totals, pace and streak from saved dictations', (
    tester,
  ) async {
    useTallScreen(tester);
    final now = DateTime.now();
    final history = FakeHistoryRepository([
      DictationEntry(
        text: List.filled(1200, 'word').join(' '),
        createdAt: now,
        duration: const Duration(minutes: 10),
      ),
    ]);
    await tester.pumpWidget(buildTestApp(history: history));
    await openTab(tester, 'Insights');

    expect(find.text('1,200'), findsOneWidget);
    expect(find.text('words dictated, all time'), findsOneWidget);
    expect(find.text('120'), findsOneWidget);
    expect(find.text('1 day'), findsOneWidget);
    expect(find.text('Longest dictation'.toUpperCase()), findsOneWidget);
  });
}
