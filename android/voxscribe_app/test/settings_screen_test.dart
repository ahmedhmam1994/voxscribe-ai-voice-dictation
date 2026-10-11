import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/features/history/domain/dictation_entry.dart';
import 'package:voxscribe_app/features/settings/domain/app_settings.dart';
import 'package:voxscribe_app/features/setup/domain/setup_status.dart';

import 'support/fake_history_repository.dart';
import 'support/fake_settings_repository.dart';
import 'support/fake_setup_platform.dart';
import 'support/scripted_engine.dart';
import 'support/test_app.dart';

ThemeMode _themeMode(WidgetTester tester) {
  return tester.widget<MaterialApp>(find.byType(MaterialApp)).themeMode!;
}

void main() {
  testWidgets('lists the sections and the language in use', (tester) async {
    useTallScreen(tester);
    await tester.pumpWidget(buildTestApp());
    await openTab(tester, 'Settings');

    expect(find.text('Floating button and permissions'), findsOneWidget);
    expect(find.text('Language you speak'), findsOneWidget);
    expect(find.text('English'), findsWidgets);
    expect(find.text('Remove filler words'), findsOneWidget);
    expect(find.text('Add a space after dictated text'), findsOneWidget);
    expect(find.text('Clear history'), findsOneWidget);
  });

  testWidgets('the setup row says how far along setup is', (tester) async {
    await tester.pumpWidget(
      buildTestApp(
        setup: FakeSetupPlatform(
          const SetupStatus(
            microphone: true,
            accessibility: false,
            overlay: false,
            bubbleRunning: false,
          ),
        ),
      ),
    );
    await openTab(tester, 'Settings');

    expect(find.textContaining('1 of 3 done'), findsOneWidget);
  });

  testWidgets('a switch changes the setting and saves it', (tester) async {
    final settings = FakeSettingsRepository();
    await tester.pumpWidget(buildTestApp(settings: settings));
    await openTab(tester, 'Settings');

    await tester.tap(find.text('Remove filler words'));
    await tester.pumpAndSettle();

    expect(settings.saved.cleanup, isFalse);
    expect(settings.saved.trailingSpace, isTrue);
  });

  testWidgets('choosing a theme switches the whole app', (tester) async {
    useTallScreen(tester);
    final settings = FakeSettingsRepository();
    await tester.pumpWidget(buildTestApp(settings: settings));
    await openTab(tester, 'Settings');
    expect(_themeMode(tester), ThemeMode.system);

    await tester.tap(find.text('Dark'));
    await tester.pumpAndSettle();
    expect(_themeMode(tester), ThemeMode.dark);
    expect(settings.saved.theme, ThemeChoice.dark);

    await tester.tap(find.text('Light'));
    await tester.pumpAndSettle();
    expect(_themeMode(tester), ThemeMode.light);
  });

  testWidgets('the saved theme is used when the app starts', (tester) async {
    final settings = FakeSettingsRepository(
      AppSettings.defaults.copyWith(theme: ThemeChoice.light),
    );
    await tester.pumpWidget(buildTestApp(settings: settings));
    await tester.pumpAndSettle();

    expect(_themeMode(tester), ThemeMode.light);
  });

  testWidgets('clearing history asks first and then clears it', (tester) async {
    useTallScreen(tester);
    final history = FakeHistoryRepository([
      DictationEntry(
        text: 'something I said',
        createdAt: DateTime.now(),
        duration: const Duration(seconds: 3),
      ),
    ]);
    await tester.pumpWidget(buildTestApp(history: history));
    await openTab(tester, 'Settings');

    await tester.tap(find.text('Clear history'));
    await tester.pumpAndSettle();
    expect(find.text('Clear history?'), findsOneWidget);

    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();
    expect(await history.load(), hasLength(1));

    await tester.tap(find.text('Clear history'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Clear'));
    await tester.pumpAndSettle();
    expect(await history.load(), isEmpty);
  });

  testWidgets('the language row opens the picker and switches language', (
    tester,
  ) async {
    final engine = ScriptedEngine();
    await tester.pumpWidget(buildTestApp(engine: engine));
    await openTab(tester, 'Settings');

    await tester.tap(find.text('Language you speak'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Arabic'));
    await tester.pumpAndSettle();

    expect(engine.languageChanges, ['ar']);
  });
}
