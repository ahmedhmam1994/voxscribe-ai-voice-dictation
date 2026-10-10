import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:voxscribe_app/features/dictation/domain/dictation_engine.dart';
import 'package:voxscribe_app/features/history/domain/dictation_entry.dart';
import 'package:voxscribe_app/features/history/history_controller.dart';
import 'package:voxscribe_app/features/dictation/domain/dictation_status.dart';

/// Holds the state of the Dictation screen and drives the engine.
class DictationController extends ChangeNotifier {
  DictationController({
    required this._engine,
    required this._history,
    this._clock = DateTime.now,
  });

  /// How many recent input levels the meter shows.
  static const meterBars = 14;

  final DictationEngine _engine;
  final HistoryController _history;
  final DateTime Function() _clock;
  StreamSubscription<double>? _levelSubscription;

  DictationStatus _status = DictationStatus.ready;
  String? _transcript;
  String? _errorMessage;
  var _language = 'en';
  var _changingLanguage = false;
  List<double> _recentLevels = const [];

  DictationStatus get status => _status;

  /// The latest dictation, or null before the first one (or after Clear).
  String? get transcript => _transcript;

  /// Set while [status] is [DictationStatus.failed].
  String? get errorMessage => _errorMessage;

  /// The last [meterBars] input levels, oldest first.
  List<double> get recentLevels => _recentLevels;

  /// The language code in use, or an empty string for automatic detection.
  String get language => _language;

  /// True while the model reloads after a language change.
  bool get changingLanguage => _changingLanguage;

  bool get canStart =>
      !_changingLanguage &&
      _status != DictationStatus.recording &&
      _status != DictationStatus.transcribing;

  /// Reads the language the engine is using.
  Future<void> loadLanguage() async {
    try {
      _language = await _engine.getLanguage();
    } on DictationException {
      // Keep the default; the picker still works.
    }
    notifyListeners();
  }

  /// Switches the language. Ignored while recording or transcribing.
  Future<void> chooseLanguage(String code) async {
    if (code == _language || !canStart) return;
    _changingLanguage = true;
    notifyListeners();
    try {
      await _engine.setLanguage(code);
      _language = code;
    } on DictationException catch (error) {
      _errorMessage = error.message;
      _status = DictationStatus.failed;
    }
    _changingLanguage = false;
    notifyListeners();
  }

  /// The user pressed and is holding the dictate button.
  Future<void> holdStarted() async {
    if (!canStart) return;
    _errorMessage = null;
    _recentLevels = const [];
    _setStatus(DictationStatus.recording);
    _levelSubscription = _engine.levels.listen(_addLevel);
    try {
      await _engine.start();
    } on DictationException catch (error) {
      await _fail(error.message);
    }
  }

  /// The user let go of the dictate button.
  Future<void> holdReleased() async {
    if (_status != DictationStatus.recording) return;
    _setStatus(DictationStatus.transcribing);
    unawaited(_stopListeningToLevels());
    try {
      final result = await _engine.stop();
      await _finish(result);
    } on DictationException catch (error) {
      await _fail(error.message);
    }
  }

  void clearTranscript() {
    _transcript = null;
    notifyListeners();
  }

  Future<void> _finish(DictationResult result) async {
    final text = result.text.trim();
    if (text.isEmpty) {
      _setStatus(DictationStatus.noSpeech);
      return;
    }
    _transcript = text;
    _setStatus(DictationStatus.ready);
    await _history.add(
      DictationEntry(
        text: text,
        createdAt: _clock(),
        duration: result.duration,
      ),
    );
  }

  Future<void> _fail(String message) async {
    await _stopListeningToLevels();
    _errorMessage = message;
    _setStatus(DictationStatus.failed);
  }

  void _addLevel(double level) {
    final next = [..._recentLevels, level.clamp(0.0, 1.0)];
    _recentLevels = next.length > meterBars
        ? next.sublist(next.length - meterBars)
        : next;
    notifyListeners();
  }

  Future<void> _stopListeningToLevels() async {
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
