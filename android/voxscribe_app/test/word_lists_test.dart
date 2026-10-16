import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/features/texttools/domain/text_tools.dart';
import 'package:voxscribe_app/features/texttools/domain/word_list_files.dart';
import 'package:voxscribe_app/features/texttools/domain/word_lists.dart';
import 'package:voxscribe_app/features/texttools/text_tools_controller.dart';

import 'support/fake_pro_repository.dart';
import 'support/fake_word_list_files.dart';

String _windowsExport({
  List<Object?> vocabulary = const [],
  List<Object?> replacements = const [],
}) => jsonEncode({
  'format': 'voxscribe-word-lists',
  'version': 1,
  'vocabulary': vocabulary,
  'replacements': replacements,
});

void main() {
  group('the word lists file', () {
    test('an export reads back the same rules', () {
      const text = 'vox scribe => VoxScribe\num =>\nc sharp => C#';
      final found = parseWordListImport(buildWordListsFile(text));
      expect(found.rules, const [
        ReplacementRule('vox scribe', 'VoxScribe'),
        ReplacementRule('um', ''),
        ReplacementRule('c sharp', 'C#'),
      ]);
      expect(found.vocabularyCount, 0);
    });

    test('is the same format the Windows app writes', () {
      final data = jsonDecode(buildWordListsFile('a med => Ahmed')) as Map;
      expect(data['format'], 'voxscribe-word-lists');
      expect(data['version'], 1);
      expect(data['vocabulary'], isEmpty);
      expect(data['replacements'], [
        {'heard': 'a med', 'replacement': 'Ahmed'},
      ]);
    });

    test('a Windows file counts the vocabulary it cannot use', () {
      final found = parseWordListImport(
        _windowsExport(
          vocabulary: ['VoxScribe', 'Zoë', 3],
          replacements: [
            {'heard': 'a', 'replacement': 'b'},
            {'heard': ''},
            'junk',
            {'heard': 'x'},
          ],
        ),
      );
      expect(found.vocabularyCount, 2);
      expect(found.rules, const [
        ReplacementRule('a', 'b'),
        ReplacementRule('x', ''),
      ]);
    });

    test('plain heard => replacement lines import too', () {
      final found = parseWordListImport(
        '﻿vox scribe => VoxScribe\nnot a rule\n',
      );
      expect(found.rules, const [ReplacementRule('vox scribe', 'VoxScribe')]);
    });

    for (final text in [
      '',
      'hello there',
      '{not json',
      '{"format": "something-else"}',
    ]) {
      test('refuses a file that is not a word list: "$text"', () {
        expect(() => parseWordListImport(text), throwsFormatException);
      });
    }
  });

  group('merging an import', () {
    test('adds new rules at the end and keeps every other line', () {
      final merge = mergeReplacements('# my list\na => b', const [
        ReplacementRule('c', 'd'),
      ]);
      expect(merge.text, '# my list\na => b\nc => d');
      expect((merge.added, merge.changed), (1, 0));
    });

    test('rewrites a rule for the same words in place', () {
      final merge = mergeReplacements('Vox Scribe => Voxscribe\nx => y', const [
        ReplacementRule('vox scribe', 'VoxScribe'),
      ]);
      expect(merge.text, 'vox scribe => VoxScribe\nx => y');
      expect((merge.added, merge.changed), (0, 1));
    });

    test('the same list twice changes nothing', () {
      const text = 'a => b\num =>';
      final merge = mergeReplacements(text, parseReplacementsText(text));
      expect(merge.text, text);
      expect((merge.added, merge.changed), (0, 0));
    });

    test('starts an empty list cleanly', () {
      final merge = mergeReplacements('', const [ReplacementRule('a', 'b')]);
      expect(merge.text, 'a => b');
    });
  });

  group('TextToolsController import and export', () {
    test('export writes the saved replacements', () async {
      final files = FakeWordListFiles();
      final controller = TextToolsController(
        repository: FakeTextToolsRepository(
          const TextToolsSettings(replacements: 'a => b\nc => d'),
        ),
        files: files,
      );

      final message = await controller.exportWordLists();

      expect(message, 'Saved 2 replacements to voxscribe-word-lists.json.');
      expect(parseWordListImport(files.savedText!).rules, hasLength(2));
    });

    test(
      'backing out of the picker says nothing and changes nothing',
      () async {
        final repository = FakeTextToolsRepository(
          const TextToolsSettings(replacements: 'a => b'),
        );
        final controller = TextToolsController(
          repository: repository,
          files: FakeWordListFiles(savedName: null),
        );

        expect(await controller.exportWordLists(), isNull);
        expect(await controller.importWordLists(), isNull);
        expect(controller.settings.replacements, 'a => b');
        expect(controller.replacementsRevision, 0);
      },
    );

    test('import merges, saves and refreshes the text box', () async {
      final repository = FakeTextToolsRepository(
        const TextToolsSettings(replacements: 'a => old'),
      );
      final controller = TextToolsController(
        repository: repository,
        files: FakeWordListFiles(
          opened: _windowsExport(
            vocabulary: ['VoxScribe'],
            replacements: [
              {'heard': 'a', 'replacement': 'new'},
              {'heard': 'c', 'replacement': 'd'},
            ],
          ),
        ),
      );

      final message = await controller.importWordLists();

      expect(
        message,
        'Added 1 replacement, changed 1. The 1 vocabulary term in it is for '
        'Windows only.',
      );
      expect(repository.saved.replacements, 'a => new\nc => d');
      expect(controller.replacementsRevision, 1);
    });

    test('a file with nothing new says so', () async {
      final controller = TextToolsController(
        repository: FakeTextToolsRepository(
          const TextToolsSettings(replacements: 'a => b'),
        ),
        files: FakeWordListFiles(opened: 'a => b'),
      );

      expect(await controller.importWordLists(), 'Nothing new in that file.');
      expect(controller.replacementsRevision, 0);
    });

    test('a wrong file or a picker error is reported', () async {
      final files = FakeWordListFiles(opened: 'hello there');
      final controller = TextToolsController(
        repository: FakeTextToolsRepository(),
        files: files,
      );

      expect(await controller.importWordLists(), startsWith('No word list'));
      files.failure = const WordListFileException('Could not read the file.');
      expect(await controller.importWordLists(), 'Could not read the file.');
    });
  });
}
