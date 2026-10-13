import 'package:flutter/foundation.dart';
import 'package:voxscribe_app/features/texttools/domain/text_tools.dart';
import 'package:voxscribe_app/features/texttools/domain/text_tools_repository.dart';

/// The text tool settings. A change shows immediately and is then saved.
class TextToolsController extends ChangeNotifier {
  TextToolsController({required this.repository});

  final TextToolsRepository repository;

  var _settings = TextToolsSettings.defaults;
  var _loaded = false;

  TextToolsSettings get settings => _settings;

  /// True once the saved values have been read, so a text box starts with them.
  bool get loaded => _loaded;

  Future<void> load() async {
    _settings = await repository.load();
    _loaded = true;
    notifyListeners();
  }

  Future<void> setVoiceCommands({required bool value}) =>
      _change(_settings.copyWith(voiceCommands: value));

  Future<void> setSmartFormat({required bool value}) =>
      _change(_settings.copyWith(smartFormat: value));

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
