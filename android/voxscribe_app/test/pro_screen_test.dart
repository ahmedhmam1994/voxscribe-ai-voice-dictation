import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/features/snippets/domain/snippet.dart';

import 'support/fake_pro_repository.dart';
import 'support/test_app.dart';

Future<void> _openPro(WidgetTester tester) async {
  await openTab(tester, 'Settings');
  await tester.tap(find.text('VoxScribe Pro').first);
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('settings says Pro is locked and what it needs', (tester) async {
    useTallScreen(tester);
    await tester.pumpWidget(buildTestApp());
    await openTab(tester, 'Settings');

    expect(
      find.textContaining('Unlock snippets with the same key'),
      findsOneWidget,
    );
  });

  testWidgets('a good key unlocks Pro and shows the features', (tester) async {
    useTallScreen(tester);
    final pro = FakeProRepository();
    await tester.pumpWidget(buildTestApp(pro: pro));
    await _openPro(tester);

    await tester.enterText(find.byType(TextField), FakeProRepository.validKey);
    await tester.tap(find.text('Unlock Pro'));
    await tester.pumpAndSettle();

    expect(find.textContaining('Pro is on'), findsOneWidget);
    expect(find.text('Snippets'), findsOneWidget);
    expect(pro.unlocked, isTrue);
  });

  testWidgets('a refused key shows the reason and stays locked', (
    tester,
  ) async {
    useTallScreen(tester);
    await tester.pumpWidget(
      buildTestApp(
        pro: FakeProRepository(failure: 'Already on another phone.'),
      ),
    );
    await _openPro(tester);

    await tester.enterText(find.byType(TextField), 'ANYTHING');
    await tester.tap(find.text('Unlock Pro'));
    await tester.pumpAndSettle();

    expect(find.text('Already on another phone.'), findsOneWidget);
    expect(find.text('Unlock Pro'), findsOneWidget);
  });

  testWidgets('Get a key opens the purchase page', (tester) async {
    useTallScreen(tester);
    final pro = FakeProRepository();
    await tester.pumpWidget(buildTestApp(pro: pro));
    await _openPro(tester);

    await tester.tap(find.text('Get a key'));
    await tester.pumpAndSettle();

    expect(pro.purchasePageOpened, isTrue);
  });

  testWidgets('snippets can be added once Pro is on', (tester) async {
    useTallScreen(tester);
    final snippets = FakeSnippetRepository();
    await tester.pumpWidget(
      buildTestApp(pro: FakeProRepository(unlocked: true), snippets: snippets),
    );
    await _openPro(tester);
    await tester.tap(find.text('Snippets'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('New snippet'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, 'When I say'), 'sig');
    await tester.enterText(
      find.widgetWithText(TextField, 'Type this'),
      'Best, Sam',
    );
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();

    expect(snippets.saved.single.trigger, 'sig');
    expect(find.text('Best, Sam'), findsOneWidget);
  });

  testWidgets('a snippet can be deleted', (tester) async {
    useTallScreen(tester);
    final snippets = FakeSnippetRepository([
      const Snippet(trigger: 'sig', expansion: 'Best, Sam'),
    ]);
    await tester.pumpWidget(
      buildTestApp(pro: FakeProRepository(unlocked: true), snippets: snippets),
    );
    await _openPro(tester);
    await tester.tap(find.text('Snippets'));
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Delete sig'));
    await tester.pumpAndSettle();

    expect(snippets.saved, isEmpty);
  });

  testWidgets('removing the license locks Pro again', (tester) async {
    useTallScreen(tester);
    final pro = FakeProRepository(unlocked: true);
    await tester.pumpWidget(buildTestApp(pro: pro));
    await _openPro(tester);

    await tester.tap(find.text('Remove license from this phone'));
    await tester.pumpAndSettle();

    expect(pro.unlocked, isFalse);
    expect(find.text('Unlock Pro'), findsOneWidget);
  });
}
