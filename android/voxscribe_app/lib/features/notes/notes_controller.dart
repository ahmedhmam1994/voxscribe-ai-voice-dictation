import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:voxscribe_app/features/dictation/domain/dictation_engine.dart';
import 'package:voxscribe_app/features/dictation/domain/dictation_status.dart';
import 'package:voxscribe_app/features/dictation/domain/no_speech_advice.dart';
import 'package:voxscribe_app/features/notes/domain/note.dart';
import 'package:voxscribe_app/features/notes/domain/notes_repository.dart';

/// The notes inbox: hold, say a thought, let go, and it is saved with the time.
/// Nothing is typed anywhere.
class NotesController extends ChangeNotifier {
  NotesController({required this._engine, required this._repository});

  static const meterBars = 14;

  final DictationEngine _engine;
  final NotesRepository _repository;
  StreamSubscription<double>? _levelSubscription;

  List<Note> _notes = const [];
  DictationStatus _status = DictationStatus.ready;
  String? _errorMessage;
  String? _noSpeech;
  List<double> _levels = const [];

  /// Newest first.
  List<Note> get notes => _notes;
  DictationStatus get status => _status;
  String? get errorMessage => _errorMessage;

  /// What to try next after a recording with no words.
  String get nothingHeardAdvice => noSpeechAdvice(_noSpeech);
  List<double> get levels => _levels;

  Future<void> load() async {
    _notes = await _repository.load();
    notifyListeners();
  }

  Future<void> holdStarted() async {
    if (_status == DictationStatus.recording ||
        _status == DictationStatus.transcribing) {
      return;
    }
    _errorMessage = null;
    _levels = const [];
    _setStatus(DictationStatus.recording);
    _levelSubscription = _engine.levels.listen(_addLevel);
    try {
      await _engine.start();
    } on DictationException catch (error) {
      await _fail(error.message);
    }
  }

  Future<void> holdReleased() async {
    if (_status != DictationStatus.recording) return;
    _setStatus(DictationStatus.transcribing);
    unawaited(_stopLevels());
    try {
      final result = await _engine.stop();
      final text = result.text.trim();
      _noSpeech = result.noSpeech;
      final note = text.isEmpty ? null : await _repository.add(text);
      if (note == null) {
        _setStatus(DictationStatus.noSpeech);
        return;
      }
      _notes = [note, ..._notes];
      _setStatus(DictationStatus.ready);
    } on DictationException catch (error) {
      await _fail(error.message);
    }
  }

  Future<void> delete(Note note) async {
    _notes = [
      for (final n in _notes)
        if (n.id != note.id) n,
    ];
    notifyListeners();
    await _repository.delete(note.id);
  }

  Future<void> share() => _repository.share();

  Future<String> markdown() => _repository.markdown();

  Future<void> _fail(String message) async {
    await _stopLevels();
    _errorMessage = message;
    _setStatus(DictationStatus.failed);
  }

  void _addLevel(double level) {
    final next = [..._levels, level.clamp(0.0, 1.0)];
    _levels = next.length > meterBars
        ? next.sublist(next.length - meterBars)
        : next;
    notifyListeners();
  }

  Future<void> _stopLevels() async {
    await _levelSubscription?.cancel();
    _levelSubscription = null;
  }

  void _setStatus(DictationStatus status) {
    _status = status;
    notifyListeners();
  }

  @override
  void dispose() {
    unawaited(_levelSubscription?.cancel());
    super.dispose();
  }
}
