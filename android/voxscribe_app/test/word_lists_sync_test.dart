import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/features/snippets/domain/snippet.dart';
import 'package:voxscribe_app/features/texttools/domain/text_tools.dart';
import 'package:voxscribe_app/features/texttools/domain/word_lists.dart';
import 'package:voxscribe_app/features/texttools/text_tools_controller.dart';

import 'support/fake_pro_repository.dart';
import 'support/fake_word_list_files.dart';

/// A version 2 file as the Windows app (core/word_lists.py) writes it.
String _windowsV2() => jsonEncode({
  'format': 'voxscribe-word-lists',
  'version': 2,
  'vocabulary': ['VoxScribe'],
  'replacements': [
    {'heard': 'vox scribe', 'replacement': 'VoxScribe'},
  ],
  'learned': [
    {'heard': 'shivon', 'fixed': 'Siobhan'},
    {'heard': 'broken'},
  ],
  'snippets': [
    {'trigger': 'my sig', 'expansion': 'Best,\nSam'},
  ],
  'templates': [
    {'name': 'bug report', 'body': 'Title: {title}\nSteps: {steps}'},
  ],
  'profile': {'field': 'medical', 'app': 'email'},
});

void main() {
  test('a version 2 file reads learned words, snippets and templates', () {
    final found = parseWordListImport(_windowsV2());
    expect(found.learned, const [ReplacementRule('shivon', 'Siobhan')]);
    expect(found.snippets.single.expansion, 'Best,\nSam');
    expect(found.templates, const [
      ReplacementRule('bug report', 'Title: {title}\nSteps: {steps}'),
    ]);
  });

  test('the export carries everything the phone has', () {
    final data = jsonDecode(
      buildWordListsFile(
        'a => b',
        templatesText: r'note => Hi\nthere',
        learnedText: 'shivon => Siobhan',
        snippets: const [Snippet(trigger: 'sig', expansion: 'Sam')],
      ),
    ) as Map;
    expect(data['version'], 2);
    expect(data['learned'], [
      {'heard': 'shivon', 'fixed': 'Siobhan'},
    ]);
    expect(data['snippets'], [
      {'trigger': 'sig', 'expansion': 'Sam'},
    ]);
    // A template line break is real in the file and \n in the box.
    expect(data['templates'], [
      {'name': 'note', 'body': 'Hi\nthere'},
    ]);
  });

  test('importing a Windows file merges everything and reports it', () async {
    final repository = FakeTextToolsRepository(
      const TextToolsSettings(templates: 'old => keep'),
    );
    final snippets = FakeSnippetRepository();
    final controller = TextToolsController(
      repository: repository,
      files: FakeWordListFiles(opened: _windowsV2()),
      snippets: snippets,
    );

    expect(
      await controller.importWordLists(),
      'Added 1 replacement, 1 template, 1 learned word, 1 snippet. '
      'The 1 vocabulary term in it is for Windows only.',
    );
    expect(repository.saved.learned, 'shivon => Siobhan');
    expect(
      repository.saved.templates,
      'old => keep\n'
      r'bug report => Title: {title}\nSteps: {steps}',
    );
    expect(snippets.saved.single.trigger, 'my sig');

    // The same file again adds nothing.
    expect(
      await controller.importWordLists(),
      startsWith('Nothing new in that file.'),
    );
  });
}
