import 'package:flutter/foundation.dart';
import 'package:voxscribe_app/features/snippets/domain/snippet.dart';
import 'package:voxscribe_app/features/snippets/domain/snippet_repository.dart';
import 'package:voxscribe_app/features/texttools/data/method_channel_word_list_files.dart';
import 'package:voxscribe_app/features/texttools/domain/corrections.dart';
import 'package:voxscribe_app/features/texttools/domain/text_tools.dart';
import 'package:voxscribe_app/features/texttools/domain/text_tools_repository.dart';
import 'package:voxscribe_app/features/texttools/domain/word_list_files.dart';
import 'package:voxscribe_app/features/texttools/domain/word_lists.dart';

/// The text tool settings. A change shows immediately and is then saved.
class TextToolsController extends ChangeNotifier {
  TextToolsController({
    required this.repository,
    WordListFiles? files,
    this.snippets,
  }) : files = files ?? MethodChannelWordListFiles();

  final TextToolsRepository repository;
  final WordListFiles files;

  /// Where snippets are kept, so the word lists file can carry them too.
  final SnippetRepository? snippets;

  var _settings = TextToolsSettings.defaults;
  var _loaded = false;
  var _replacementsRevision = 0;

  TextToolsSettings get settings => _settings;

  /// True once the saved values have been read, so a text box starts with them.
  bool get loaded => _loaded;

  /// Goes up when the replacements change from outside the text box (an
  /// import), so the box starts again with the new text.
  int get replacementsRevision => _replacementsRevision;

  Future<void> load() async {
    _settings = await repository.load();
    _loaded = true;
    notifyListeners();
  }

  Future<void> setVoiceCommands({required bool value}) =>
      _change(_settings.copyWith(voiceCommands: value));

  Future<void> setSmartFormat({required bool value}) =>
      _change(_settings.copyWith(smartFormat: value));

  /// Adds `heard => replacement` to the word replacements, or updates the
  /// rule for the same heard words. Waits for the saved values to be read
  /// first, so a correction can never overwrite the rules already there.
  Future<CorrectionStatus> addCorrection(
    String heard,
    String replacement,
  ) async {
    if (!_loaded) await load();
    final result = applyCorrection(_settings.replacements, heard, replacement);
    if (result.status == CorrectionStatus.added ||
        result.status == CorrectionStatus.updated) {
      await _change(_settings.copyWith(replacements: result.text));
    }
    return result.status;
  }

  /// Saves the word replacements, learned words, snippets and templates to
  /// a file the user picks. Returns what to tell the user, or null when they
  /// backed out.
  Future<String?> exportWordLists() async {
    if (!_loaded) await load();
    final snippetList = await snippets?.load() ?? const <Snippet>[];
    final counts = {
      'replacement': parseReplacementsText(_settings.replacements).length,
      'learned word': parseReplacementsText(_settings.learned).length,
      'snippet': snippetList.length,
      'template': parseReplacementsText(_settings.templates).length,
    };
    try {
      final name = await files.save(
        wordListsFileName,
        buildWordListsFile(
          _settings.replacements,
          templatesText: _settings.templates,
          learnedText: _settings.learned,
          snippets: snippetList,
        ),
      );
      if (name == null) return null;
      final parts = [
        for (final MapEntry(key: what, value: n) in counts.entries)
          if (n > 0) '$n $what${n == 1 ? '' : 's'}',
      ];
      return 'Saved ${parts.isEmpty ? 'your settings' : parts.join(', ')} '
          'to $name.';
    } on WordListFileException catch (e) {
      return e.message;
    }
  }

  /// Adds what is in a file the user picks: word replacements, learned
  /// words, snippets and templates. Returns what to tell the user, or null
  /// when they backed out.
  Future<String?> importWordLists() async {
    if (!_loaded) await load();
    final String? text;
    try {
      text = await files.open();
    } on WordListFileException catch (e) {
      return e.message;
    }
    if (text == null) return null;
    final WordListImport found;
    try {
      found = parseWordListImport(text);
    } on FormatException catch (e) {
      return e.message;
    }
    final report = <String>[];
    var next = _settings;

    final merge = mergeReplacements(next.replacements, found.rules);
    if (merge.added > 0 || merge.changed > 0) {
      next = next.copyWith(replacements: merge.text);
      final changed = merge.changed == 0 ? '' : ' (${merge.changed} changed)';
      report.add(
        '${merge.added} replacement${merge.added == 1 ? '' : 's'}$changed',
      );
    }

    if (found.templates.isNotEmpty) {
      final templates = mergeReplacements(
        next.templates,
        templateLines(found.templates),
      );
      final n = templates.added + templates.changed;
      if (n > 0) {
        next = next.copyWith(templates: templates.text);
        report.add('$n template${n == 1 ? '' : 's'}');
      }
    }

    if (found.learned.isNotEmpty) {
      final before = parseReplacementsText(next.learned).toSet();
      final learned = await repository.addLearned(found.learned);
      final n = parseReplacementsText(learned)
          .toSet()
          .difference(before)
          .length;
      next = next.copyWith(learned: learned);
      if (n > 0) report.add('$n learned word${n == 1 ? '' : 's'}');
    }

    final snippetStore = snippets;
    if (found.snippets.isNotEmpty && snippetStore != null) {
      final saved = [...await snippetStore.load()];
      var n = 0;
      for (final incoming in found.snippets) {
        final at = saved.indexWhere((s) => s.hasSameTrigger(incoming));
        if (at < 0) {
          saved.add(incoming);
          n++;
        } else if (saved[at].expansion != incoming.expansion) {
          saved[at] = incoming;
          n++;
        }
      }
      if (n > 0) {
        await snippetStore.save(saved);
        report.add('$n snippet${n == 1 ? '' : 's'}');
      }
    }

    final skipped = found.vocabularyCount == 0
        ? ''
        : ' The ${found.vocabularyCount} vocabulary '
              'term${found.vocabularyCount == 1 ? '' : 's'} in it '
              '${found.vocabularyCount == 1 ? 'is' : 'are'} for Windows only.';
    if (report.isEmpty) return 'Nothing new in that file.$skipped';
    _replacementsRevision++;
    await _change(next);
    return 'Added ${report.join(', ')}.$skipped';
  }

  Future<void> setMode(String value) =>
      _change(_settings.copyWith(mode: value));

  Future<void> setAutoModes({required bool value}) =>
      _change(_settings.copyWith(autoModes: value));

  Future<void> setSendIt({required bool value}) =>
      _change(_settings.copyWith(sendIt: value));

  Future<void> setCodeDictation({required bool value}) =>
      _change(_settings.copyWith(codeDictation: value));

  /// Switches one term pack on or off, keeping the order the others were turned on in.
  Future<void> setTermPackEnabled(String id, {required bool enabled}) {
    final ids = _settings.enabledPacks.where((other) => other != id).toList();
    if (enabled) ids.add(id);
    return _change(_settings.copyWith(termPacks: ids.join(',')));
  }

  Future<void> setSpokenFormats({required bool value}) =>
      _change(_settings.copyWith(spokenFormats: value));

  Future<void> setReadBack({required bool value}) =>
      _change(_settings.copyWith(readBack: value));

  Future<void> setFormFill({required bool value}) =>
      _change(_settings.copyWith(formFill: value));

  Future<void> setScreenSpelling({required bool value}) =>
      _change(_settings.copyWith(screenSpelling: value));

  Future<void> setLearnFixes({required bool value}) =>
      _change(_settings.copyWith(learnFixes: value));

  /// Reads the learned fixes again: the floating button learns them while
  /// this screen is not open.
  Future<void> refreshLearned() async {
    final saved = await repository.load();
    _settings = _settings.copyWith(learned: saved.learned);
    notifyListeners();
  }

  /// Removes one learned fix; it is spelled as heard again from then on.
  Future<void> forgetLearned(String heard) async {
    final left = await repository.forgetLearned(heard);
    _settings = _settings.copyWith(learned: left);
    notifyListeners();
  }

  Future<void> setReplacements(String value) =>
      _change(_settings.copyWith(replacements: value));

  Future<void> setTemplates(String value) =>
      _change(_settings.copyWith(templates: value));

  Future<void> setProfiles(String value) =>
      _change(_settings.copyWith(profiles: value));

  Future<void> _change(TextToolsSettings next) {
    _settings = next;
    notifyListeners();
    return repository.save(next);
  }
}
