import 'package:flutter/foundation.dart';
import 'package:voxscribe_app/features/setup/domain/setup_platform.dart';
import 'package:voxscribe_app/features/setup/domain/setup_status.dart';

/// Holds the setup state and performs the next action for the user.
class SetupController extends ChangeNotifier {
  SetupController({required this.platform});

  final SetupPlatform platform;

  SetupStatus _status = SetupStatus.none;
  String? _errorMessage;
  var _busy = false;

  SetupStatus get status => _status;

  /// A short explanation of the last failed action, or null.
  String? get errorMessage => _errorMessage;

  bool get busy => _busy;

  /// Re-reads the phone's state. Call when the app returns from a system
  /// screen or permission dialog.
  Future<void> refresh() async {
    try {
      _status = await platform.getStatus();
    } on SetupException catch (error) {
      _errorMessage = error.message;
    }
    notifyListeners();
  }

  /// Does what the primary button says: the next permission step, or turns
  /// the floating button on or off once every step is done.
  Future<void> performPrimaryAction() async {
    if (_busy) return;
    _busy = true;
    _errorMessage = null;
    notifyListeners();
    try {
      await _run(_status.nextStep);
    } on SetupException catch (error) {
      _errorMessage = error.message;
    }
    _busy = false;
    await refresh();
  }

  Future<void> _run(SetupStep? step) {
    return switch (step) {
      SetupStep.microphone => platform.requestMicrophone(),
      SetupStep.accessibility => platform.openAccessibilitySettings(),
      SetupStep.overlay => platform.openOverlaySettings(),
      null => platform.setBubbleRunning(running: !_status.bubbleRunning),
    };
  }
}
