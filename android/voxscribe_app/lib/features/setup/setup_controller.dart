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
  var _loaded = false;
  var _reminderHidden = false;

  SetupStatus get status => _status;

  /// The phone's state has been read at least once, so [status] is real.
  bool get loaded => _loaded;

  /// Whether the Dictation screen should point new users to the setup steps:
  /// until every step is done and the floating button is on, unless they
  /// chose Not now in this session.
  bool get showReminder =>
      _loaded &&
      !_reminderHidden &&
      !(_status.permissionsComplete && _status.bubbleRunning);

  /// Not now: hides the Dictation screen's setup card until the app restarts.
  void hideReminder() {
    _reminderHidden = true;
    notifyListeners();
  }

  /// Call when the setup screen opens.
  Future<void> opened() async {
    try {
      await platform.setupOpened();
    } on SetupException {
      // Only feeds the usage ping; never worth showing.
    }
  }

  /// A short explanation of the last failed action, or null.
  String? get errorMessage => _errorMessage;

  bool get busy => _busy;

  /// Re-reads the phone's state. Call when the app returns from a system
  /// screen or permission dialog.
  Future<void> refresh() async {
    try {
      _status = await platform.getStatus();
      _loaded = true;
    } on SetupException catch (error) {
      _errorMessage = error.message;
    }
    notifyListeners();
  }

  /// Opens the notification settings for this app.
  Future<void> openNotificationSettings() =>
      _open(platform.openNotificationSettings);

  /// Opens App info, where a restricted accessibility switch is allowed.
  Future<void> openAppInfo() {
    _triedSwitch = false;
    return _open(platform.openAppInfo);
  }

  Future<void> openAccessibilitySettings() {
    _triedSwitch = true;
    return _open(platform.openAccessibilitySettings);
  }

  var _triedSwitch = false;

  /// The accessibility switch may be a Restricted setting and the user came
  /// back from it without turning VoxScribe on, so most likely Android
  /// blocked it and the next step is allowing it in App info. Android shows
  /// that choice in App info only after its warning.
  bool get appInfoNext =>
      _triedSwitch &&
      _status.accessibilityRestricted &&
      _status.nextStep == SetupStep.accessibility;

  Future<void> _open(Future<void> Function() action) async {
    try {
      await action();
    } on SetupException catch (error) {
      _errorMessage = error.message;
      notifyListeners();
    }
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
    final appInfo = appInfoNext;
    if (step == SetupStep.accessibility) _triedSwitch = !appInfo;
    return switch (step) {
      SetupStep.microphone => platform.requestMicrophone(),
      SetupStep.accessibility when appInfo => platform.openAppInfo(),
      SetupStep.accessibility => platform.openAccessibilitySettings(),
      SetupStep.overlay => platform.openOverlaySettings(),
      null => platform.setBubbleRunning(running: !_status.bubbleRunning),
    };
  }
}
