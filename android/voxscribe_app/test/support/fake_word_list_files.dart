import 'package:voxscribe_app/features/texttools/domain/word_list_files.dart';

/// Stands in for Android's file picker. [opened] is what the user "picks";
/// null means they backed out. [savedText] is what was written.
class FakeWordListFiles implements WordListFiles {
  FakeWordListFiles({
    this.opened,
    this.savedName = 'voxscribe-word-lists.json',
  });

  String? opened;
  String? savedName;
  String? savedText;
  WordListFileException? failure;

  @override
  Future<String?> save(String fileName, String text) async {
    if (failure != null) throw failure!;
    if (savedName == null) return null;
    savedText = text;
    return savedName;
  }

  @override
  Future<String?> open() async {
    if (failure != null) throw failure!;
    return opened;
  }
}
