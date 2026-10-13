import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/features/texttools/domain/text_tools.dart';
import 'package:voxscribe_app/features/texttools/text_tools_controller.dart';

import 'support/fake_pro_repository.dart';
import 'support/test_app.dart';

Future<void> _openTextTools(WidgetTester tester) async {
  await openTab(tester, 'Settings');
  await tester.tap(find.text('Voice commands, replacements and more'));
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

  group('Text tools page', () {
    testWidgets('settings links to it', (tester) async {
      useTallScreen(tester);
      await tester.pumpWidget(buildTestApp());

      await _openTextTools(tester);

      expect(find.text('Text tools'), findsWidgets);
      expect(find.text('Voice commands'), findsOneWidget);
      expect(find.text('WORD REPLACEMENTS'), findsOneWidget);
    });

    testWidgets('voice commands can be switched on and are saved', (
      tester,
    ) async {
      useTallScreen(tester);
      final repository = FakeTextToolsRepository();
      await tester.pumpWidget(buildTestApp(textTools: repository));
      await _openTextTools(tester);

      await tester.tap(find.text('Voice commands'));
      await tester.pumpAndSettle();

      expect(repository.saved.voiceCommands, isTrue);
    });

    testWidgets('typing a replacement is saved', (tester) async {
      useTallScreen(tester);
      final repository = FakeTextToolsRepository();
      await tester.pumpWidget(buildTestApp(textTools: repository));
      await _openTextTools(tester);

      await tester.enterText(
        find.widgetWithText(TextField, 'Heard => replacement'),
        'vox scribe => VoxScribe',
      );
      await tester.pumpAndSettle();

      expect(repository.saved.replacements, 'vox scribe => VoxScribe');
    });

    testWidgets('the boxes start with what was saved', (tester) async {
      useTallScreen(tester);
      final repository = FakeTextToolsRepository(
        const TextToolsSettings(replacements: 'cat => dog'),
      );
      await tester.pumpWidget(buildTestApp(textTools: repository));
      await _openTextTools(tester);

      expect(find.text('cat => dog'), findsOneWidget);
    });

    testWidgets('Pro tools are locked without Pro', (tester) async {
      useTallScreen(tester);
      final repository = FakeTextToolsRepository();
      await tester.pumpWidget(buildTestApp(textTools: repository));
      await _openTextTools(tester);

      expect(find.text('PRO (LOCKED)'), findsOneWidget);
      expect(
        find.textContaining('Unlock Pro with the same key'),
        findsOneWidget,
      );

      await tester.tap(find.text('Smart formatting'), warnIfMissed: false);
      await tester.pumpAndSettle();

      expect(repository.saved.smartFormat, isFalse);
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
      await _openTextTools(tester);

      await tester.tap(find.text('Smart formatting'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Code dictation'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.widgetWithText(TextField, 'App package => options'),
        'com.termux => code=on',
      );
      await tester.pumpAndSettle();

      expect(repository.saved.smartFormat, isTrue);
      expect(repository.saved.codeDictation, isTrue);
      expect(repository.saved.profiles, 'com.termux => code=on');
      expect(find.text('PRO'), findsOneWidget);
    });
  });
}
