import 'package:flutter/foundation.dart';

/// A language the speech models can type.
@immutable
class DictationLanguage {
  const DictationLanguage({required this.code, required this.name});

  /// The code the phone side saves, such as `en` or `ar`.
  final String code;
  final String name;
}

/// The choices in the language picker. Nemotron types Arabic and Turkish,
/// Granite types the rest (see SpeechEngine.kt). There
/// is no auto-detect: each model types best when it knows the language.
const dictationLanguages = [
  DictationLanguage(code: 'en', name: 'English'),
  DictationLanguage(code: 'ar', name: 'Arabic'),
  DictationLanguage(code: 'tr', name: 'Turkish'),
  DictationLanguage(code: 'fr', name: 'French'),
  DictationLanguage(code: 'es', name: 'Spanish'),
  DictationLanguage(code: 'de', name: 'German'),
  DictationLanguage(code: 'it', name: 'Italian'),
  DictationLanguage(code: 'pt', name: 'Portuguese'),
];

/// The entry for [code], or English when the code is unknown.
DictationLanguage languageForCode(String code) {
  return dictationLanguages.firstWhere(
    (language) => language.code == code,
    orElse: () => dictationLanguages.first,
  );
}
