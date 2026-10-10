import 'package:flutter/foundation.dart';

/// The permissions the floating button needs, in the order the user does them.
enum SetupStep { microphone, accessibility, overlay }

/// What the phone currently allows, and whether the floating button is on.
@immutable
class SetupStatus {
  const SetupStatus({
    required this.microphone,
    required this.accessibility,
    required this.overlay,
    required this.bubbleRunning,
  });

  /// Nothing granted yet.
  static const none = SetupStatus(
    microphone: false,
    accessibility: false,
    overlay: false,
    bubbleRunning: false,
  );

  final bool microphone;
  final bool accessibility;
  final bool overlay;
  final bool bubbleRunning;

  bool isDone(SetupStep step) => switch (step) {
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
    );
  }
}
