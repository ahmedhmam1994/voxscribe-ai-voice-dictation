import 'package:flutter/foundation.dart';
import 'package:voxscribe_app/features/texttools/data/method_channel_word_list_files.dart';
import 'package:voxscribe_app/features/texttools/domain/corrections.dart';
import 'package:voxscribe_app/features/texttools/domain/text_tools.dart';
import 'package:voxscribe_app/features/texttools/domain/text_tools_repository.dart';
import 'package:voxscribe_app/features/texttools/domain/word_list_files.dart';
import 'package:voxscribe_app/features/texttools/domain/word_lists.dart';

/// The text tool settings. A change shows immediately and is then saved.
class TextToolsController extends ChangeNotifier {
  TextToolsController({required this.repository, WordListFiles? files})
    : files = files ?? MethodChannelWordListFiles();

  final TextToolsRepository repository;
  final WordListFiles files;

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

  /// Saves the word replacements to a file the user picks. Returns what to
  /// tell the user, or null when they backed out.
  Future<String?> exportWordLists() async {
    if (!_loaded) await load();
    final count = parseReplacementsText(_settings.replacements).length;
    try {
      final name = await files.save(
        wordListsFileName,
        buildWordListsFile(_settings.replacements),
      );
      if (name == null) return null;
      return 'Saved $count replacement${count == 1 ? '' : 's'} to $name.';
    } on WordListFileException catch (e) {
      return e.message;
    }
  }

  /// Adds the rules from a file the user picks to the word replacements.
  /// Returns what to tell the user, or null when they backed out.
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
    final merge = mergeReplacements(_settings.replacements, found.rules);
    final skipped = found.vocabularyCount == 0
        ? ''
        : ' The ${found.vocabularyCount} vocabulary '
              'term${found.vocabularyCount == 1 ? '' : 's'} in it '
              '${found.vocabularyCount == 1 ? 'is' : 'are'} for Windows only.';
    if (merge.added == 0 && merge.changed == 0) {
      return 'Nothing new in that file.$skipped';
    }
    _replacementsRevision++;
    await _change(_settings.copyWith(replacements: merge.text));
    final changed = merge.changed == 0 ? '' : ', changed ${merge.changed}';
    return 'Added ${merge.added} '
        'replacement${merge.added == 1 ? '' : 's'}$changed.$skipped';
  }

  Future<void> setSendIt({required bool value}) =>
      _change(_settings.copyWith(sendIt: value));

  Future<void> setCodeDictation({required bool value}) =>
      _change(_settings.copyWith(codeDictation: value));

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
