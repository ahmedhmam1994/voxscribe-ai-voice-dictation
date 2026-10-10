import 'package:flutter/foundation.dart';

/// One finished dictation.
@immutable
class DictationEntry {
  const DictationEntry({
    required this.text,
    required this.createdAt,
    required this.duration,
  });

  final String text;
  final DateTime createdAt;
  final Duration duration;

  int get wordCount {
    final trimmed = text.trim();
    return trimmed.isEmpty ? 0 : trimmed.split(RegExp(r'\s+')).length;
  }
}
