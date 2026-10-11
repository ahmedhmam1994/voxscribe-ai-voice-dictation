import 'package:flutter/foundation.dart';

/// Which theme the app uses.
enum ThemeChoice { system, light, dark }

/// The user's saved choices.
@immutable
class AppSettings {
  const AppSettings({
    required this.cleanup,
    required this.trailingSpace,
    required this.theme,
  });

  /// What a fresh install uses.
  static const defaults = AppSettings(
    cleanup: true,
    trailingSpace: true,
    theme: ThemeChoice.system,
  );

  /// Remove filler words such as "um" and "uh" from dictations.
  final bool cleanup;

  /// Add a space after dictated text so the next dictation does not run into it.
  final bool trailingSpace;

  final ThemeChoice theme;

  AppSettings copyWith({
    bool? cleanup,
    bool? trailingSpace,
    ThemeChoice? theme,
  }) {
    return AppSettings(
      cleanup: cleanup ?? this.cleanup,
      trailingSpace: trailingSpace ?? this.trailingSpace,
      theme: theme ?? this.theme,
    );
  }
}
