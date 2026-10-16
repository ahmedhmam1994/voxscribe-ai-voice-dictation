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
    this.usagePing = true,
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

  /// Once a day, an anonymous "the app was used" ping: versions and a random id only.
  final bool usagePing;

  AppSettings copyWith({
    bool? cleanup,
    bool? trailingSpace,
    ThemeChoice? theme,
    bool? usagePing,
  }) {
    return AppSettings(
      cleanup: cleanup ?? this.cleanup,
      trailingSpace: trailingSpace ?? this.trailingSpace,
      theme: theme ?? this.theme,
      usagePing: usagePing ?? this.usagePing,
    );
  }
}
