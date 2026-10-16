import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/features/dictation/widgets/today_list.dart';
import 'package:voxscribe_app/features/history/domain/dictation_entry.dart';
import 'package:voxscribe_app/features/texttools/domain/corrections.dart';
import 'package:voxscribe_app/features/texttools/domain/text_tools.dart';
import 'package:voxscribe_app/features/texttools/text_tools_controller.dart';

import 'support/fake_history_repository.dart';
import 'support/fake_pro_repository.dart';
import 'support/test_app.dart';

void main() {
  group('cleanHeard', () {
    test('drops punctuation and spaces around the words', () {
      expect(cleanHeard('  whisker,  '), 'whisker');
      expect(cleanHeard('"Hello there."'), 'Hello there');
      expect(cleanHeard('...'), '');
    });

    test('keeps apostrophes and hyphens inside a word', () {
      expect(cleanHeard("don't"), "don't");
      expect(cleanHeard('well-known,'), 'well-known');
    });

    test('squeezes the gaps between words', () {
      expect(cleanHeard('vox\n  scribe'), 'vox scribe');
    });
  });

  group('wordsOf', () {
    test('lists the words with their punctuation, skipping bare symbols', () {
      expect(wordsOf('Meet me, at -- noon.'), ['Meet', 'me,', 'at', 'noon.']);
    });
  });

  group('applyCorrection', () {
    test('adds the first rule', () {
      final r = applyCorrection('', 'noon,', 'one');
      expect(r.text, 'noon => one');
      expect(r.status, CorrectionStatus.added);
    });

    test('adds below the rules already there and leaves them alone', () {
      final r = applyCorrection('vox scribe => VoxScribe\n', 'noon', 'one');
      expect(r.text, 'vox scribe => VoxScribe\nnoon => one');
      expect(r.status, CorrectionStatus.added);
    });

    test('updating a rule replaces it instead of adding a second', () {
      final r = applyCorrection('a => b\nNoon => one\nc => d', 'noon', 'two');
      expect(r.text, 'a => b\nnoon => two\nc => d');
      expect(r.status, CorrectionStatus.updated);
    });

    test('the same rule again changes nothing', () {
      final r = applyCorrection('noon => one', 'Noon', 'one');
      expect(r.text, 'noon => one');
      expect(r.status, CorrectionStatus.unchanged);
    });

    test('empty or identical corrections are refused', () {
      expect(
        applyCorrection('x => y', 'noon', '   ').status,
        CorrectionStatus.invalid,
      );
      expect(
        applyCorrection('x => y', '  ', 'one').status,
        CorrectionStatus.invalid,
      );
      expect(
        applyCorrection('x => y', 'noon', 'noon').status,
        CorrectionStatus.invalid,
      );
      expect(applyCorrection('x => y', 'noon', 'noon').text, 'x => y');
    });

    test('a line break in the answer becomes a space', () {
      expect(applyCorrection('', 'a b', 'c\nd').text, 'a b => c d');
    });
  });

  group('TextToolsController.addCorrection', () {
    test('waits for the saved rules, so it never overwrites them', () async {
      final repository = FakeTextToolsRepository(
        const TextToolsSettings(replacements: 'keep => me'),
      );
      final controller = TextToolsController(repository: repository);

      final status = await controller.addCorrection('noon', 'one');

      expect(status, CorrectionStatus.added);
      expect(repository.saved.replacements, 'keep => me\nnoon => one');
    });
  });

  testWidgets('fixing a word from today\'s history saves a replacement', (
    tester,
  ) async {
    useTallScreen(tester);
    final repository = FakeTextToolsRepository();
    final history = FakeHistoryRepository([
      DictationEntry(
        text: 'Meet me at noon, please.',
        createdAt: DateTime.now(),
        duration: const Duration(seconds: 3),
      ),
    ]);
    await tester.pumpWidget(
      buildTestApp(textTools: repository, history: history),
    );
    await tester.pumpAndSettle();

    await tester.tap(
      find.descendant(
        of: find.byType(TodayList),
        matching: find.text('Fix a word'),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Tap the word that was heard wrong.'), findsOneWidget);

    await tester.tap(find.widgetWithText(ChoiceChip, 'noon,'));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.widgetWithText(TextField, 'Type this instead'),
      'one',
    );
    await tester.tap(find.text('Save correction'));
    await tester.pumpAndSettle();

    expect(repository.saved.replacements, 'noon => one');
    expect(
      find.textContaining('VoxScribe will type "one" instead of "noon"'),
      findsOneWidget,
    );
  });
}
