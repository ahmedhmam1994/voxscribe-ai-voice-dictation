import 'dart:async';

import 'package:voxscribe_app/features/dictation/domain/dictation_engine.dart';

/// An engine the test drives by hand: it decides when recording starts and
/// what transcription returns.
class ScriptedEngine implements DictationEngine {
  final _levels = StreamController<double>.broadcast();
  Completer<DictationResult>? _transcription;

  /// The language the engine reports, and the ones it was asked to switch to.
  String language = 'en';
  final languageChanges = <String>[];

  /// Make the next [start] throw this.
  DictationException? startError;

  @override
  Stream<double> get levels => _levels.stream;

  void emitLevel(double level) => _levels.add(level);

  /// Completes the transcription started by [stop].
  void finish(String text, {Duration duration = const Duration(seconds: 2)}) {
    _transcription!.complete(DictationResult(text: text, duration: duration));
  }

  /// Fails the transcription started by [stop].
  void fail(String message) {
    _transcription!.completeError(DictationException(message));
  }

  @override
  Future<String> getLanguage() async => language;

  @override
  Future<void> setLanguage(String code) async {
    language = code;
    languageChanges.add(code);
  }

  @override
  Future<void> start() async {
    final error = startError;
    if (error != null) throw error;
  }

  @override
  Future<DictationResult> stop() {
    _transcription = Completer<DictationResult>();
    return _transcription!.future;
  }
}
