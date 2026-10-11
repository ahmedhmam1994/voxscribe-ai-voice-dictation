import 'package:voxscribe_app/features/snippets/domain/snippet.dart';

/// Where the user's snippets are saved. The native typing code reads the
/// same list, so a snippet works from the floating button too.
abstract interface class SnippetRepository {
  Future<List<Snippet>> load();

  Future<void> save(List<Snippet> snippets);
}
