import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/app/theme/app_theme.dart';
import 'package:voxscribe_app/features/settings/leaver_question_sheet.dart';

import 'support/fake_settings_repository.dart';

Widget _host(FakeSettingsRepository repository) {
  return MaterialApp(
    theme: AppTheme.light,
    home: Scaffold(
      body: Builder(
        builder: (context) => TextButton(
          onPressed: () => showLeaverQuestionSheet(context, repository),
          child: const Text('open'),
        ),
      ),
    ),
  );
}

void main() {
  testWidgets('picking an answer sends its fixed key', (tester) async {
    final repository = FakeSettingsRepository()..leaverDue = true;
    await tester.pumpWidget(_host(repository));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();

    expect(find.text('Quick question'), findsOneWidget);
    await tester.tap(find.text('It was too slow'));
    await tester.pumpAndSettle();

    expect(repository.leaverAnswered, isTrue);
    expect(repository.leaverReason, 'too_slow');
    expect(find.text('Thanks, that helps.'), findsOneWidget);
    expect(await repository.leaverQuestionDue(), isFalse);
  });

  testWidgets("don't ask marks it asked and sends nothing", (tester) async {
    final repository = FakeSettingsRepository()..leaverDue = true;
    await tester.pumpWidget(_host(repository));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();

    await tester.tap(find.text("Don't ask"));
    await tester.pumpAndSettle();

    expect(repository.leaverAnswered, isTrue);
    expect(repository.leaverReason, isNull);
    expect(find.text('Thanks, that helps.'), findsNothing);
  });

  test('every answer key matches the native list', () {
    expect(leaverReasons.map((r) => r.$1), [
      'wrong_words',
      'too_slow',
      'no_text',
      'button_in_way',
      'button_gone',
      'forgot',
      'rarely_need',
      'busy',
      'other',
    ]);
  });
}
