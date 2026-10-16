/// Lets the user pick where a word lists file is saved, or which one to open,
/// with the phone's own file picker.
abstract interface class WordListFiles {
  /// Saves [text] to a file the user picks, starting with [fileName].
  /// Returns the saved file's name, or null when the user backs out.
  Future<String?> save(String fileName, String text);

  /// The text of a file the user picks, or null when the user backs out.
  Future<String?> open();
}

/// A file could not be read or written.
class WordListFileException implements Exception {
  const WordListFileException(this.message);

  final String message;

  @override
  String toString() => message;
}
