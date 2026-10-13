import 'package:voxscribe_app/features/texttools/domain/text_tools.dart';

/// Where the text tool settings are saved. The native typing code reads the
/// same values, so they apply from the floating button too.
abstract interface class TextToolsRepository {
  Future<TextToolsSettings> load();

  Future<void> save(TextToolsSettings settings);
}
