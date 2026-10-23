import 'package:flutter/foundation.dart';

/// Which theme the app uses.
enum ThemeChoice { system, light, dark }

/// How the floating button reacts to a touch: hold to talk, tap to start and
/// tap to stop, or both (a quick tap latches, a longer press is a hold).
enum RecordingMode { both, hold, tap }

/// How big the floating button is. [medium] is the size of earlier versions.
enum BubbleSize { small, medium, large }

/// The user's saved choices.
@immutable
class AppSettings {
  const AppSettings({
    required this.cleanup,
    required this.trailingSpace,
    required this.theme,
    this.usagePing = true,
    this.recordingMode = RecordingMode.both,
    this.bubbleSize = BubbleSize.medium,
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

  /// How a touch on the floating button starts and stops a dictation.
  final RecordingMode recordingMode;

  /// The size of the floating button.
  final BubbleSize bubbleSize;

  AppSettings copyWith({
    bool? cleanup,
    bool? trailingSpace,
    ThemeChoice? theme,
    bool? usagePing,
    RecordingMode? recordingMode,
    BubbleSize? bubbleSize,
  }) {
    return AppSettings(
      cleanup: cleanup ?? this.cleanup,
      trailingSpace: trailingSpace ?? this.trailingSpace,
      theme: theme ?? this.theme,
      usagePing: usagePing ?? this.usagePing,
      recordingMode: recordingMode ?? this.recordingMode,
      bubbleSize: bubbleSize ?? this.bubbleSize,
    );
  }
}
