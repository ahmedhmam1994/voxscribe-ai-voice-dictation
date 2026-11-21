import 'package:flutter/foundation.dart';

/// A language the speech models can type.
@immutable
class DictationLanguage {
  const DictationLanguage({
    required this.code,
    required this.name,
    required this.native,
    this.granite = false,
  });

  /// The code the phone side saves, such as `en` or `ar`.
  final String code;
  final String name;

  /// The language's name in its own words, such as 日本語.
  final String native;

  /// Typed by Granite (the English and European model); the rest by Nemotron.
  final bool granite;
}

/// The choices in the language picker, the same codes as SpeechEngine.kt.
/// Each was checked on synthetic speech before it was added (21 Nov 2026).
/// There is no auto-detect: each model types best when it knows the language.
/// English and Arabic first, then by name.
const dictationLanguages = [
  DictationLanguage(
    code: 'en',
    name: 'English',
    native: 'English',
    granite: true,
  ),
  DictationLanguage(code: 'ar', name: 'Arabic', native: 'العربية'),
  DictationLanguage(code: 'zh', name: 'Chinese', native: '中文'),
  DictationLanguage(code: 'cs', name: 'Czech', native: 'Čeština'),
  DictationLanguage(code: 'nl', name: 'Dutch', native: 'Nederlands'),
  DictationLanguage(code: 'fi', name: 'Finnish', native: 'Suomi'),
  DictationLanguage(
    code: 'fr',
    name: 'French',
    native: 'Français',
    granite: true,
  ),
  DictationLanguage(
    code: 'de',
    name: 'German',
    native: 'Deutsch',
    granite: true,
  ),
  DictationLanguage(code: 'hi', name: 'Hindi', native: 'हिन्दी'),
  DictationLanguage(code: 'hu', name: 'Hungarian', native: 'Magyar'),
  DictationLanguage(
    code: 'it',
    name: 'Italian',
    native: 'Italiano',
    granite: true,
  ),
  DictationLanguage(code: 'ja', name: 'Japanese', native: '日本語'),
  DictationLanguage(code: 'ko', name: 'Korean', native: '한국어'),
  DictationLanguage(code: 'pl', name: 'Polish', native: 'Polski'),
  DictationLanguage(
    code: 'pt',
    name: 'Portuguese',
    native: 'Português',
    granite: true,
  ),
  DictationLanguage(code: 'ru', name: 'Russian', native: 'Русский'),
  DictationLanguage(code: 'sk', name: 'Slovak', native: 'Slovenčina'),
  DictationLanguage(
    code: 'es',
    name: 'Spanish',
    native: 'Español',
    granite: true,
  ),
  DictationLanguage(code: 'tr', name: 'Turkish', native: 'Türkçe'),
  DictationLanguage(code: 'uk', name: 'Ukrainian', native: 'Українська'),
  DictationLanguage(code: 'vi', name: 'Vietnamese', native: 'Tiếng Việt'),
];

/// The entry for [code], or English when the code is unknown.
DictationLanguage languageForCode(String code) {
  return dictationLanguages.firstWhere(
    (language) => language.code == code,
    orElse: () => dictationLanguages.first,
  );
}
