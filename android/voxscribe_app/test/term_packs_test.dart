import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/app/theme/app_theme.dart';
import 'package:voxscribe_app/features/termpacks/domain/term_packs.dart';
import 'package:voxscribe_app/features/termpacks/teach_voice_page.dart';
import 'package:voxscribe_app/features/termpacks/term_packs_controller.dart';
import 'package:voxscribe_app/features/termpacks/term_packs_page.dart';
import 'package:voxscribe_app/features/texttools/domain/text_tools.dart';
import 'package:voxscribe_app/features/texttools/text_tools_controller.dart';

import 'support/fake_pro_repository.dart';

import 'package:voxscribe_app/features/setup/domain/setup_platform.dart';

import 'support/fake_setup_platform.dart';
import 'support/fake_word_list_files.dart';
import 'support/scripted_engine.dart';
import 'support/test_app.dart';

/// Packs and Teach your voice without the native side.
class FakeTermPacks implements TermPacksPlatform {
  final packs = <TermPack>[
    const TermPack(id: 'medical', label: 'Medical', count: 330),
    const TermPack(id: 'legal', label: 'Law', count: 210),
  ];
  var script = const [
    TeachLine('Her TSH was high, so she started levothyroxine.', [
      'TSH',
      'levothyroxine',
    ]),
  ];
  final imported = <(String, String)>[];
  final removed = <String>[];

  /// What the comparison answers for any reading.
  var proposals = const <TeachProposal>[];

  @override
  Future<List<TermPack>> list() async => List.of(packs);

  @override
  Future<TermPack> import(String fileName, String text) async {
    if (text.trim().isEmpty) {
      throw const TermPackException('No terms found.');
    }
    imported.add((fileName, text));
    final pack = TermPack(
      id: 'user:$fileName',
      label: fileName,
      count: text.trim().split('\n').length,
      user: true,
    );
    packs.add(pack);
    return pack;
  }

  @override
  Future<void> remove(String id) async {
    removed.add(id);
    packs.removeWhere((p) => p.id == id);
  }

  @override
  Future<List<TeachLine>> teachScript() async => script;

  @override
  Future<List<TeachProposal>> teachProposals(
    List<(TeachLine, String)> readings,
  ) async => proposals;
}

void main() {
  group('TextToolsController packs', () {
    test('switching packs keeps the order they were turned on in', () async {
      final repo = FakeTextToolsRepository();
      final tools = TextToolsController(repository: repo);
      await tools.setTermPackEnabled('legal', enabled: true);
      await tools.setTermPackEnabled('medical', enabled: true);
      expect(repo.saved.enabledPacks, ['legal', 'medical']);
      await tools.setTermPackEnabled('legal', enabled: false);
      expect(repo.saved.termPacks, 'medical');
    });

    test('spoken formats and read back are off by default and save', () async {
      expect(TextToolsSettings.defaults.spokenFormats, isFalse);
      expect(TextToolsSettings.defaults.readBack, isFalse);
      final repo = FakeTextToolsRepository();
      final tools = TextToolsController(repository: repo);
      await tools.setSpokenFormats(value: true);
      await tools.setReadBack(value: true);
      expect(repo.saved.spokenFormats, isTrue);
      expect(repo.saved.readBack, isTrue);
    });
  });

  group('TermPacksController', () {
    test('imports a picked file under the name given', () async {
      final platform = FakeTermPacks();
      final files = FakeWordListFiles(opened: 'Dr. Okafor\nNorthside Clinic');
      final packs = TermPacksController(platform: platform, files: files);
      final message = await packs.importPack(askName: () async => 'Clinic');
      expect(platform.imported.single.$1, 'Clinic');
      expect(message, 'Added Clinic, 2 terms. Switch it on to use it.');
      expect(packs.packs.last.user, isTrue);
    });

    test('backing out of the picker or the name does nothing', () async {
      final platform = FakeTermPacks();
      final picker = TermPacksController(
        platform: platform,
        files: FakeWordListFiles(),
      );
      expect(await picker.importPack(askName: () async => 'x'), isNull);
      final named = TermPacksController(
        platform: platform,
        files: FakeWordListFiles(opened: 'a'),
      );
      expect(await named.importPack(askName: () async => null), isNull);
      expect(platform.imported, isEmpty);
    });

    test('an empty file says why', () async {
      final packs = TermPacksController(
        platform: FakeTermPacks(),
        files: FakeWordListFiles(opened: '  '),
      );
      expect(
        await packs.importPack(askName: () async => 'Empty'),
        'No terms found.',
      );
    });
  });

  Widget host(Widget child) => MaterialApp(theme: AppTheme.dark, home: child);

  testWidgets('the packs page switches packs and spoken formats', (
    tester,
  ) async {
    useTallScreen(tester);
    final repo = FakeTextToolsRepository();
    final tools = TextToolsController(repository: repo);
    await tester.pumpWidget(
      host(
        TermPacksPage(
          packs: TermPacksController(platform: FakeTermPacks()),
          textTools: tools,
          engine: ScriptedEngine(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Medical'), findsOneWidget);
    expect(find.text('330 terms'), findsOneWidget);
    await tester.tap(find.text('Medical'));
    await tester.pump();
    expect(repo.saved.enabledPacks, ['medical']);

    await tester.tap(find.text('Spoken formats for the packs'));
    await tester.pump();
    expect(repo.saved.spokenFormats, isTrue);
  });

  testWidgets('Teach your voice turns ticked slips into replacements', (
    tester,
  ) async {
    useTallScreen(tester);
    final engine = ScriptedEngine();
    final platform = FakeTermPacks()
      ..proposals = const [
        TeachProposal(heard: 'levoseroxine', expected: 'levothyroxine'),
      ];
    final repo = FakeTextToolsRepository();
    final tools = TextToolsController(repository: repo);
    await tester.pumpWidget(
      host(
        TeachVoicePage(engine: engine, platform: platform, textTools: tools),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Sentence 1 of 1'), findsOneWidget);
    await tester.tap(find.text('Start recording'));
    await tester.pump();
    await tester.tap(find.text('Stop'));
    await tester.pump();
    engine.finish('Her TSH was high, so she started levoseroxine.');
    await tester.pumpAndSettle();

    expect(
      find.textContaining('“levoseroxine” (meant levothyroxine)'),
      findsOneWidget,
    );
    await tester.tap(find.text('See results'));
    await tester.pumpAndSettle();
    expect(find.text('“levoseroxine”  →  levothyroxine'), findsOneWidget);

    await tester.tap(find.text('Add to my word replacements'));
    await tester.pumpAndSettle();
    expect(repo.saved.replacements, 'levoseroxine => levothyroxine');
  });

  testWidgets('Teach your voice with nothing read has nothing to learn', (
    tester,
  ) async {
    await tester.pumpWidget(
      host(
        TeachVoicePage(
          engine: ScriptedEngine(),
          platform: FakeTermPacks(),
          textTools: TextToolsController(repository: FakeTextToolsRepository()),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Skip this one'));
    await tester.pumpAndSettle();
    expect(find.textContaining('nothing to learn yet'), findsOneWidget);
  });

  testWidgets('settings offer the Quick Settings tile and term packs', (
    tester,
  ) async {
    useTallScreen(tester);
    final setup = FakeSetupPlatform()..tileResult = QuickTileResult.manual;
    await tester.pumpWidget(buildTestApp(setup: setup));
    await tester.pumpAndSettle();
    await openTab(tester, 'Settings');

    expect(find.text('Term packs'), findsOneWidget);
    expect(find.text('Read it back'), findsOneWidget);
    await tester.tap(find.text('Quick Settings tile'));
    await tester.pumpAndSettle();
    expect(setup.calls, contains('addQuickTile'));
    expect(find.textContaining('tap the pencil'), findsOneWidget);
  });

  testWidgets('says so when the tile is already in Quick Settings', (
    WidgetTester tester,
  ) async {
    useTallScreen(tester);
    final setup = FakeSetupPlatform()
      ..tileResult = QuickTileResult.alreadyAdded;
    await tester.pumpWidget(buildTestApp(setup: setup));
    await tester.pumpAndSettle();
    await openTab(tester, 'Settings');

    await tester.tap(find.text('Quick Settings tile'));
    await tester.pumpAndSettle();
    expect(find.textContaining('already in your tiles'), findsOneWidget);
  });
}
