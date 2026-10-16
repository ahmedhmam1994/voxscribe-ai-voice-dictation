import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/features/settings/widgets/settings_group.dart';
import 'package:voxscribe_app/features/texttools/domain/text_tools.dart';
import 'package:voxscribe_app/features/texttools/text_tools_controller.dart';

import 'support/fake_pro_repository.dart';
import 'support/test_app.dart';

/// Opens Settings and taps the row called [title], scrolling to it first.
Future<void> _openRow(WidgetTester tester, String title) async {
  await openTab(tester, 'Settings');
  final row = find.text(title);
  await tester.scrollUntilVisible(
    row,
    200,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.tap(row);
  await tester.pumpAndSettle();
}

/// Flips the switch row called [title] on the open page.
Future<void> _flip(WidgetTester tester, String title) async {
  await tester.tap(find.widgetWithText(SettingsSwitchRow, title));
  await tester.pumpAndSettle();
}

void main() {
  group('TextToolsController', () {
    test('starts with everything off and nothing listed', () {
      final controller = TextToolsController(
        repository: FakeTextToolsRepository(),
      );

      expect(controller.settings, TextToolsSettings.defaults);
      expect(controller.loaded, isFalse);
    });

    test('loads what is saved', () async {
      const saved = TextToolsSettings(
        voiceCommands: true,
        replacements: 'vox scribe => VoxScribe',
      );
      final controller = TextToolsController(
        repository: FakeTextToolsRepository(saved),
      );

      await controller.load();

      expect(controller.loaded, isTrue);
      expect(controller.settings, saved);
    });

    test('a change shows at once and is saved', () async {
      final repository = FakeTextToolsRepository();
      final controller = TextToolsController(repository: repository);
      var notified = 0;
      controller.addListener(() => notified++);

      await controller.setVoiceCommands(value: true);
      await controller.setCodeDictation(value: true);
      await controller.setTemplates('hi => Hello');

      expect(controller.settings.voiceCommands, isTrue);
      expect(controller.settings.codeDictation, isTrue);
      expect(repository.saved.templates, 'hi => Hello');
      expect(repository.saved.voiceCommands, isTrue);
      expect(notified, 3);
    });

    test('each setter changes only its own value', () async {
      final repository = FakeTextToolsRepository();
      final controller = TextToolsController(repository: repository);

      await controller.setSmartFormat(value: true);
      await controller.setReplacements('a => b');
      await controller.setProfiles('com.x => code=on');

      expect(
        repository.saved,
        const TextToolsSettings(
          smartFormat: true,
          replacements: 'a => b',
          profiles: 'com.x => code=on',
        ),
      );
    });
  });

  group('Settings groups and tool pages', () {
    testWidgets('settings shows each tool in its own group', (tester) async {
      useTallScreen(tester);
      await tester.pumpWidget(buildTestApp());
      await openTab(tester, 'Settings');

      for (final title in [
        'Voice commands',
        'Say "send it" to send',
        'Your replacements',
        'Smart formatting',
        'Code dictation',
        'Fill-in templates',
        'Per-app profiles',
      ]) {
        await tester.scrollUntilVisible(
          find.text(title),
          200,
          scrollable: find.byType(Scrollable).first,
        );
        expect(find.text(title), findsOneWidget);
      }
      expect(find.text('Voice commands, replacements and more'), findsNothing);
    });

    testWidgets('the voice commands page lists every command and switches on', (
      tester,
    ) async {
      useTallScreen(tester);
      final repository = FakeTextToolsRepository();
      await tester.pumpWidget(buildTestApp(textTools: repository));
      await _openRow(tester, 'Voice commands');

      expect(find.text('"scratch that"'), findsOneWidget);
      expect(find.text('"all caps"'), findsOneWidget);
      expect(find.text('"new paragraph"'), findsOneWidget);
      await _flip(tester, 'Voice commands');

      expect(repository.saved.voiceCommands, isTrue);
    });

    testWidgets('settings says whether voice commands are on', (tester) async {
      useTallScreen(tester);
      await tester.pumpWidget(
        buildTestApp(
          textTools: FakeTextToolsRepository(
            const TextToolsSettings(
              voiceCommands: true,
              replacements: 'a => b\nc => d',
            ),
          ),
        ),
      );
      await openTab(tester, 'Settings');

      expect(
        find.text('On. Punctuation, take back, change it.'),
        findsOneWidget,
      );
      await tester.scrollUntilVisible(
        find.text('2 replacements'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.text('2 replacements'), findsOneWidget);
    });

    testWidgets('typing a replacement is saved', (tester) async {
      useTallScreen(tester);
      final repository = FakeTextToolsRepository();
      await tester.pumpWidget(buildTestApp(textTools: repository));
      await _openRow(tester, 'Your replacements');

      await tester.enterText(
        find.widgetWithText(TextField, 'Heard => replacement'),
        'vox scribe => VoxScribe',
      );
      await tester.pumpAndSettle();

      expect(repository.saved.replacements, 'vox scribe => VoxScribe');
    });

    testWidgets('the replacements box starts with what was saved', (
      tester,
    ) async {
      useTallScreen(tester);
      final repository = FakeTextToolsRepository(
        const TextToolsSettings(replacements: 'cat => dog'),
      );
      await tester.pumpWidget(buildTestApp(textTools: repository));
      await _openRow(tester, 'Your replacements');

      expect(find.text('cat => dog'), findsOneWidget);
      expect(find.widgetWithText(OutlinedButton, 'Import'), findsOneWidget);
      expect(find.widgetWithText(OutlinedButton, 'Export'), findsOneWidget);
    });

    testWidgets('Pro tools are locked without Pro', (tester) async {
      useTallScreen(tester);
      final repository = FakeTextToolsRepository();
      await tester.pumpWidget(buildTestApp(textTools: repository));
      await openTab(tester, 'Settings');
      await tester.scrollUntilVisible(
        find.text('Smart formatting'),
        200,
        scrollable: find.byType(Scrollable).first,
      );

      expect(find.textContaining('Locked. Unlock snippets'), findsOneWidget);
      await tester.tap(find.text('Smart formatting'), warnIfMissed: false);
      await tester.pumpAndSettle();
      expect(repository.saved.smartFormat, isFalse);

      await tester.scrollUntilVisible(
        find.text('Fill-in templates'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.tap(find.text('Fill-in templates'));
      await tester.pumpAndSettle();
      expect(find.textContaining('Pro (locked)'), findsOneWidget);
      final templates = tester.widget<TextField>(
        find.widgetWithText(TextField, 'Name => text with {slots}'),
      );
      expect(templates.enabled, isFalse);
    });

    testWidgets('Pro tools work once Pro is unlocked', (tester) async {
      useTallScreen(tester);
      final repository = FakeTextToolsRepository();
      await tester.pumpWidget(
        buildTestApp(
          textTools: repository,
          pro: FakeProRepository(unlocked: true),
        ),
      );
      await openTab(tester, 'Settings');
      await tester.scrollUntilVisible(
        find.text('Code dictation'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.textContaining('Unlocked. Snippets'), findsOneWidget);
      await _flip(tester, 'Smart formatting');
      await _flip(tester, 'Code dictation');
      await _openRow(tester, 'Per-app profiles');
      await tester.enterText(
        find.widgetWithText(TextField, 'App package => options'),
        'com.termux => code=on',
      );
      await tester.pumpAndSettle();

      expect(repository.saved.smartFormat, isTrue);
      expect(repository.saved.codeDictation, isTrue);
      expect(repository.saved.profiles, 'com.termux => code=on');
    });
  });

  group('send it', () {
    test('is off until the user turns it on, and is saved', () async {
      final repository = FakeTextToolsRepository();
      final controller = TextToolsController(repository: repository);

      expect(controller.settings.sendIt, isFalse);
      await controller.setSendIt(value: true);

      expect(controller.settings.sendIt, isTrue);
      expect(repository.saved.sendIt, isTrue);
    });

    testWidgets('has its own page with a switch', (tester) async {
      useTallScreen(tester);
      final repository = FakeTextToolsRepository();
      await tester.pumpWidget(buildTestApp(textTools: repository));
      await _openRow(tester, 'Say "send it" to send');

      expect(find.textContaining('reads button names only'), findsOneWidget);
      await _flip(tester, 'Say "send it" to send');

      expect(repository.saved.sendIt, isTrue);
      expect(repository.saved.voiceCommands, isFalse);
    });
  });
}
