import 'package:voxscribe_app/features/texttools/domain/text_tools.dart';
import 'package:voxscribe_app/features/texttools/domain/word_lists.dart';

/// Where the text tool settings are saved. The native typing code reads the
/// same values, so they apply from the floating button too.
abstract interface class TextToolsRepository {
  Future<TextToolsSettings> load();

  Future<void> save(TextToolsSettings settings);

  /// Removes the learned fix for [heard]. Returns the learned fixes left.
  Future<String> forgetLearned(String heard);

  /// Keeps fixes learned on another device, with the same rules as a fix
  /// learned here. Returns all learned fixes.
  Future<String> addLearned(List<ReplacementRule> fixes);
}
