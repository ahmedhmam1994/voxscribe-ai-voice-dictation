/// One transcribed file: its name, the text and the captions as .srt.
class FileImportResult {
  const FileImportResult({
    required this.name,
    required this.text,
    required this.srt,
  });

  final String name;
  final String text;
  final String srt;
}

/// What a folder run did.
class FolderImportResult {
  const FolderImportResult({
    required this.done,
    required this.failed,
    required this.total,
    required this.saved,
    required this.cancelled,
  });

  final int done;
  final int failed;

  /// How many audio and video files the folder had, or -1 when cancelled early.
  final int total;

  /// The names of the files written next to the originals.
  final List<String> saved;
  final bool cancelled;
}

/// Whether folders are unlocked, and how many free folder runs are left.
class FolderStatus {
  const FolderStatus({required this.pro, required this.runsLeft});

  final bool pro;
  final int runsLeft;

  bool get allowed => pro || runsLeft > 0;
}

/// Progress of the file being transcribed.
class ImportProgress {
  const ImportProgress({
    required this.name,
    required this.atSeconds,
    required this.lengthSeconds,
    required this.index,
    required this.total,
  });

  final String name;

  /// How far into the current file, and its length (0 when unknown).
  final double atSeconds;
  final double lengthSeconds;

  /// 0 to 1 for the current file, or null when its length is unknown.
  double? get fraction =>
      lengthSeconds > 0 ? (atSeconds / lengthSeconds).clamp(0.0, 1.0) : null;

  /// Which file of a folder run, from 0.
  final int index;
  final int total;
}

/// Thrown when a folder run needs Pro.
class ImportNeedsPro implements Exception {
  const ImportNeedsPro(this.message);

  final String message;
}

/// Thrown when a file or folder could not be transcribed.
class ImportFailed implements Exception {
  const ImportFailed(this.message);

  final String message;
}

/// Transcribes audio and video files on the phone. Every call opens Android's
/// own picker, so the app only sees what the user picks.
abstract interface class FileImportRepository {
  Stream<ImportProgress> get progress;

  Future<FolderStatus> folderStatus();

  /// Null when the user backed out of the picker or cancelled.
  Future<FileImportResult?> transcribeFile();

  /// Null when the user backed out of the picker.
  Future<FolderImportResult?> transcribeFolder({
    required bool srt,
    required bool txt,
  });

  /// Saves [text] where the user picks. Returns the saved name, or null.
  Future<String?> save({
    required String name,
    required String text,
    required String mime,
  });

  Future<void> cancel();
}
