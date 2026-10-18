import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:voxscribe_app/features/import/domain/file_import.dart';

/// Transcribing one file or a folder, and what to show while it runs.
class FileImportController extends ChangeNotifier {
  FileImportController({required this.repository}) {
    _sub = repository.progress.listen((p) {
      _progress = p;
      notifyListeners();
    });
  }

  final FileImportRepository repository;
  late final StreamSubscription<ImportProgress> _sub;

  var _busy = false;
  ImportProgress? _progress;
  FileImportResult? _file;
  FolderImportResult? _folder;
  FolderStatus _status = const FolderStatus(pro: false, runsLeft: 0);
  String? _message;
  var _saveSrt = true;
  var _saveTxt = false;

  bool get busy => _busy;
  ImportProgress? get progress => _progress;

  /// The last single file transcribed.
  FileImportResult? get file => _file;

  /// The last folder run.
  FolderImportResult? get folder => _folder;
  FolderStatus get status => _status;

  /// A note or error to show, or null.
  String? get message => _message;

  bool get saveSrt => _saveSrt;
  bool get saveTxt => _saveTxt;

  Future<void> load() async {
    _status = await repository.folderStatus();
    notifyListeners();
  }

  void setSaveSrt({required bool value}) {
    if (!value && !_saveTxt) return; // a folder run must save something
    _saveSrt = value;
    notifyListeners();
  }

  void setSaveTxt({required bool value}) {
    if (!value && !_saveSrt) return;
    _saveTxt = value;
    notifyListeners();
  }

  Future<void> transcribeFile() => _run(() async {
    final result = await repository.transcribeFile();
    if (result == null) return;
    _file = result;
    _folder = null;
    if (result.text.isEmpty) {
      _message = 'No speech was found in ${result.name}.';
    }
  });

  Future<void> transcribeFolder() => _run(() async {
    final result = await repository.transcribeFolder(
      srt: _saveSrt,
      txt: _saveTxt,
    );
    if (result == null) return;
    _folder = result;
    _file = null;
    _status = await repository.folderStatus();
    _message = _folderSummary(result);
  });

  Future<void> cancel() => repository.cancel();

  /// Saves the single file's text or captions. Returns what to tell the user.
  Future<void> saveFile({required bool captions}) async {
    final result = _file;
    if (result == null) return;
    final base = result.name.contains('.')
        ? result.name.substring(0, result.name.lastIndexOf('.'))
        : result.name;
    try {
      final saved = await repository.save(
        name: captions ? '$base.srt' : '$base.txt',
        text: captions ? result.srt : result.text,
        mime: captions ? 'application/x-subrip' : 'text/plain',
      );
      if (saved != null) _message = 'Saved $saved.';
    } on ImportFailed catch (e) {
      _message = e.message;
    }
    notifyListeners();
  }

  Future<void> _run(Future<void> Function() body) async {
    if (_busy) return;
    _busy = true;
    _message = null;
    _progress = null;
    notifyListeners();
    try {
      await body();
    } on ImportNeedsPro catch (e) {
      _message = e.message;
    } on ImportFailed catch (e) {
      _message = e.message;
    } finally {
      _busy = false;
      _progress = null;
      notifyListeners();
    }
  }

  static String _folderSummary(FolderImportResult r) {
    if (r.cancelled) return 'Stopped. ${r.done} done before you cancelled.';
    if (r.total == 0) return 'That folder has no audio or video files.';
    final failed = r.failed == 0 ? '' : ' ${r.failed} could not be read.';
    final files = r.saved.length == 1 ? 'file' : 'files';
    return 'Transcribed ${r.done} of ${r.total}. Saved ${r.saved.length} '
        '$files next to the originals.$failed';
  }

  @override
  void dispose() {
    _sub.cancel();
    super.dispose();
  }
}
