import 'package:flutter/foundation.dart';

/// A language the speech model can transcribe.
@immutable
class DictationLanguage {
  const DictationLanguage({required this.code, required this.name});

  /// Whisper's language code, or an empty string to detect it automatically.
  final String code;
  final String name;
}

/// The choices in the language picker. English is first because it is the
/// default: automatic detection sometimes guesses the wrong language on a
/// phone microphone.
const dictationLanguages = [
  DictationLanguage(code: 'en', name: 'English'),
  DictationLanguage(code: 'ar', name: 'Arabic'),
  DictationLanguage(code: '', name: 'Auto-detect'),
  DictationLanguage(code: 'fr', name: 'French'),
  DictationLanguage(code: 'es', name: 'Spanish'),
  DictationLanguage(code: 'de', name: 'German'),
  DictationLanguage(code: 'it', name: 'Italian'),
  DictationLanguage(code: 'tr', name: 'Turkish'),
];

/// The entry for [code], or English when the code is unknown.
DictationLanguage languageForCode(String code) {
  return dictationLanguages.firstWhere(
    (language) => language.code == code,
    orElse: () => dictationLanguages.first,
  );
}
