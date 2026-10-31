import 'package:flutter/foundation.dart';
import 'package:voxscribe_app/features/termpacks/data/method_channel_term_packs.dart';
import 'package:voxscribe_app/features/termpacks/domain/term_packs.dart';
import 'package:voxscribe_app/features/texttools/data/method_channel_word_list_files.dart';
import 'package:voxscribe_app/features/texttools/domain/word_list_files.dart';

/// The term packs on this phone. Which ones are on is a text tool setting
/// (see `TextToolsController.setTermPackEnabled`).
class TermPacksController extends ChangeNotifier {
  TermPacksController({TermPacksPlatform? platform, WordListFiles? files})
    : platform = platform ?? MethodChannelTermPacks(),
      files = files ?? MethodChannelWordListFiles();

  final TermPacksPlatform platform;
  final WordListFiles files;

  var _packs = const <TermPack>[];

  List<TermPack> get packs => _packs;

  Future<void> load() async {
    _packs = await platform.list();
    notifyListeners();
  }

  /// Adds a pack from a text file the user picks, named with [askName].
  /// Returns what to tell the user, or null when they backed out.
  Future<String?> importPack({
    required Future<String?> Function() askName,
  }) async {
    final String? text;
    try {
      text = await files.open();
    } on WordListFileException catch (e) {
      return e.message;
    }
    if (text == null) return null;
    final name = await askName();
    if (name == null) return null;
    try {
      final pack = await platform.import(name, text);
      await load();
      return 'Added ${pack.label}, ${pack.count} '
          'term${pack.count == 1 ? '' : 's'}. Switch it on to use it.';
    } on TermPackException catch (e) {
      return e.message;
    }
  }

  Future<void> remove(TermPack pack) async {
    await platform.remove(pack.id);
    await load();
  }
}
