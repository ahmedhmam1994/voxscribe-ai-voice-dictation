import 'package:voxscribe_app/features/notes/domain/note.dart';

/// Where the notes inbox is kept: on this phone only.
abstract interface class NotesRepository {
  /// Newest first.
  Future<List<Note>> load();

  /// Saves [text] as a note. Null when there were no words to keep.
  Future<Note?> add(String text);

  Future<void> delete(int id);

  /// The whole inbox as markdown, the same file the Windows app writes.
  Future<String> markdown();

  /// Opens the phone's share sheet with the inbox as markdown.
  Future<void> share();
}
