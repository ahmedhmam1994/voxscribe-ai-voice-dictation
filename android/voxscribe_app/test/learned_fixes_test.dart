import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/features/texttools/domain/text_tools.dart';
import 'package:voxscribe_app/features/texttools/text_tools_controller.dart';

import 'support/fake_pro_repository.dart';
import 'support/test_app.dart';

void main() {
  test('learning is on by default and the switch saves', () async {
    expect(TextToolsSettings.defaults.learnFixes, isTrue);
    final repo = FakeTextToolsRepository();
    final tools = TextToolsController(repository: repo);
    await tools.setLearnFixes(value: false);
    expect(repo.saved.learnFixes, isFalse);
  });

  testWidgets('learned fixes are listed and one can be removed', (
    tester,
  ) async {
    final repo = FakeTextToolsRepository(
      const TextToolsSettings(
        learned: 'Shivon => Siobhan\nvox scribe => VoxScribe',
      ),
    );
    useTallScreen(tester);
    await tester.pumpWidget(buildTestApp(textTools: repo));
    await tester.pumpAndSettle();
    await openTab(tester, 'Settings');
    await tester.ensureVisible(find.text('Your replacements'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Your replacements'));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(
      find.text('Shivon → Siobhan'),
      200,
      scrollable: find.byType(Scrollable).last,
    );

    expect(find.text('Learn from my fixes'), findsOneWidget);
    expect(find.text('vox scribe → VoxScribe'), findsOneWidget);

    await tester.tap(find.byTooltip('Remove Shivon'));
    await tester.pumpAndSettle();

    expect(find.text('Shivon → Siobhan'), findsNothing);
    expect(repo.saved.learned, 'vox scribe => VoxScribe');
  });

  test('a fix learned while the app was closed shows when reloaded', () async {
    final repo = FakeTextToolsRepository();
    final tools = TextToolsController(repository: repo);
    await tools.load();
    repo.saved = repo.saved.copyWith(learned: 'Shivon => Siobhan');
    await tools.refreshLearned();
    expect(tools.settings.learned, 'Shivon => Siobhan');
  });
}
