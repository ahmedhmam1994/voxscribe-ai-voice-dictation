import 'package:flutter/foundation.dart';

/// What dictation needs, in the order the user does it: the speech model for
/// their language, then the permissions the floating button needs.
enum SetupStep { model, microphone, accessibility, overlay }

/// What the phone currently allows, and whether the floating button is on.
@immutable
class SetupStatus {
  const SetupStatus({
    required this.microphone,
    required this.accessibility,
    required this.overlay,
    required this.bubbleRunning,
    this.accessibilityNeedsRestart = false,
    this.accessibilityRestricted = false,
    this.notifications = true,
    this.setupSeen = true,
    this.bubbleUsed = true,
    this.batteryUnrestricted = true,
    this.xiaomi = false,
    this.language = 'en',
    this.modelInstalled = true,
    this.modelDownloading = false,
    this.modelPercent = 0,
    this.modelMegabytes = 0,
    this.modelError,
  });

  /// Nothing granted yet.
  static const none = SetupStatus(
    microphone: false,
    accessibility: false,
    overlay: false,
    bubbleRunning: false,
    modelInstalled: false,
  );

  final bool microphone;
  final bool accessibility;
  final bool overlay;
  final bool bubbleRunning;

  /// Whether VoxScribe may show notifications. The floating button works
  /// without them, but the hide and show button and the warning that the
  /// typing service disconnected both need them.
  final bool notifications;

  /// Accessibility is switched on, but Android has disconnected the service,
  /// as it can after an app update. Switching it off and on fixes it.
  final bool accessibilityNeedsRestart;

  /// VoxScribe was installed from a file, so Android 13+ may grey out the
  /// accessibility switch ("Restricted setting") until it is allowed in App
  /// info. Android does not tell apps whether it is still blocked.
  final bool accessibilityRestricted;

  /// The setup screen has been opened on this phone before. A new install
  /// starts on the setup steps until then.
  final bool setupSeen;

  /// The floating button has been pressed at least once. Until then the app
  /// offers a practice box, because the button only shows over a text box.
  final bool bubbleUsed;

  /// Battery saving is off for VoxScribe, so Android will not stop the
  /// floating button in the background. Not required, but without it some
  /// phones close the button after a while.
  final bool batteryUnrestricted;

  /// A Xiaomi, Redmi or Poco phone, whose own battery saver sits on top of
  /// Android's and needs "No restrictions" in App info as well.
  final bool xiaomi;

  /// The language the user speaks, as a code from `dictationLanguages`.
  final String language;

  /// The speech model for [language] is on the phone. Dictation needs it.
  final bool modelInstalled;

  /// That model is downloading. It counts as started, so the steps after it
  /// can be done meanwhile.
  final bool modelDownloading;

  /// How far the download is, 0 to 100.
  final int modelPercent;

  /// The size of the download.
  final int modelMegabytes;

  /// Why the last download stopped, or null.
  final String? modelError;

  bool isDone(SetupStep step) => switch (step) {
    SetupStep.model => modelInstalled || modelDownloading,
    SetupStep.microphone => microphone,
    SetupStep.accessibility => accessibility,
    SetupStep.overlay => overlay,
  };

  /// The first step still to do, or null when all are done.
  SetupStep? get nextStep {
    for (final step in SetupStep.values) {
      if (!isDone(step)) return step;
    }
    return null;
  }

  int get doneCount => SetupStep.values.where(isDone).length;

  bool get permissionsComplete => nextStep == null;

  SetupStatus copyWith({bool? bubbleRunning}) {
    return SetupStatus(
      microphone: microphone,
      accessibility: accessibility,
      overlay: overlay,
      bubbleRunning: bubbleRunning ?? this.bubbleRunning,
      accessibilityNeedsRestart: accessibilityNeedsRestart,
      accessibilityRestricted: accessibilityRestricted,
      notifications: notifications,
      setupSeen: setupSeen,
      bubbleUsed: bubbleUsed,
      batteryUnrestricted: batteryUnrestricted,
      xiaomi: xiaomi,
      language: language,
      modelInstalled: modelInstalled,
      modelDownloading: modelDownloading,
      modelPercent: modelPercent,
      modelMegabytes: modelMegabytes,
      modelError: modelError,
    );
  }
}
