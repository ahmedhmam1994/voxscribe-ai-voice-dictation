import 'package:flutter/foundation.dart';

/// The outcome of one recording.
@immutable
class DictationResult {
  const DictationResult({
    required this.text,
    required this.duration,
    this.noSpeech,
  });

  /// Empty when no speech was recognized.
  final String text;
  final Duration duration;

  /// Why [text] is empty, when it is: too_short, silent, quiet or unclear.
  final String? noSpeech;
}

/// Thrown when the engine cannot record or transcribe.
class DictationException implements Exception {
  const DictationException(this.message, {this.modelMissing = false});

  final String message;

  /// The speech model for the language is not downloaded yet.
  final bool modelMissing;

  @override
  String toString() => message;
}

/// Records speech and turns it into text. The real implementation talks to
/// the native engine; tests and previews use a fake.
abstract interface class DictationEngine {
  /// Input level from 0 to 1, emitted while recording.
  Stream<double> get levels;

  Future<void> start();

  /// Stops recording and transcribes it.
  Future<DictationResult> stop();

  /// The language code in use, or an empty string for automatic detection.
  Future<String> getLanguage();

  /// Switches the language. Can take a moment while the model reloads.
  Future<void> setLanguage(String code);
}
