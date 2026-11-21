import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:voxscribe_app/features/setup/domain/setup_platform.dart';
import 'package:voxscribe_app/features/setup/domain/setup_status.dart';

/// Holds the setup state and performs the next action for the user.
class SetupController extends ChangeNotifier {
  SetupController({required this.platform, this.onLanguageChanged});

  final SetupPlatform platform;

  /// Called after the language is changed here, so the Dictation screen
  /// shows the new one.
  final VoidCallback? onLanguageChanged;

  // Reads the download's progress while the speech model downloads.
  Timer? _modelPoll;

  SetupStatus _status = SetupStatus.none;
  String? _errorMessage;
  var _busy = false;
  var _loaded = false;
  var _reminderHidden = false;
  var _firstRun = false;
  var _practiceHidden = false;

  SetupStatus get status => _status;

  /// The phone's state has been read at least once, so [status] is real.
  bool get loaded => _loaded;

  /// Whether the Dictation screen should point new users to the setup steps:
  /// until every step is done and the floating button is on, and while the
  /// speech model downloads, unless they chose Not now in this session.
  bool get showReminder =>
      _loaded &&
      !_firstRun &&
      !_reminderHidden &&
      (!(_status.permissionsComplete && _status.bubbleRunning) ||
          _status.modelDownloading);

  /// Not now: hides the Dictation screen's setup card until the app restarts.
  void hideReminder() {
    _reminderHidden = true;
    notifyListeners();
  }

  /// A new install: the Dictation screen shows the setup steps instead of
  /// itself until the user finishes them (practice included) or skips.
  bool get firstRun => _firstRun;

  /// Skip for now, or the practice is done: back to the Dictation screen.
  void finishFirstRun() {
    _firstRun = false;
    notifyListeners();
  }

  /// Offer the practice box: every step is done and the floating button is
  /// on, but it has never been pressed.
  bool get showPractice =>
      _loaded &&
      !_practiceHidden &&
      _status.permissionsComplete &&
      _status.bubbleRunning &&
      !_status.bubbleUsed;

  /// Done or Skip on the practice box. Also ends the first run.
  void hidePractice() {
    _practiceHidden = true;
    _firstRun = false;
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
      final firstLook = !_loaded;
      _status = await platform.getStatus();
      _loaded = true;
      _watchDownload();
      if (firstLook && !_status.setupSeen && !_status.permissionsComplete) {
        _firstRun = true;
      }
      // Pressed the button in another app: the first run has done its job.
      if (_firstRun &&
          _status.permissionsComplete &&
          _status.bubbleRunning &&
          _status.bubbleUsed) {
        _firstRun = false;
      }
    } on SetupException catch (error) {
      _errorMessage = error.message;
    }
    notifyListeners();
  }

  void _watchDownload() {
    if (_status.modelDownloading) {
      _modelPoll ??= Timer.periodic(
        const Duration(seconds: 1),
        (_) => unawaited(refresh()),
      );
    } else {
      _modelPoll?.cancel();
      _modelPoll = null;
    }
  }

  @override
  void dispose() {
    _modelPoll?.cancel();
    super.dispose();
  }

  /// Starts the speech model download for the chosen language.
  Future<void> downloadModel() async {
    await _open(platform.downloadModel);
    await refresh();
  }

  /// Stops the speech model download.
  Future<void> cancelModelDownload() async {
    await _open(platform.cancelModel);
    await refresh();
  }

  /// Changes the language the user speaks, which picks the speech model.
  Future<void> chooseLanguage(String code) async {
    if (code == _status.language || _busy) return;
    _busy = true;
    notifyListeners();
    await _open(() => platform.setLanguage(code));
    _busy = false;
    await refresh();
    onLanguageChanged?.call();
  }

  /// Opens the notification settings for this app.
  Future<void> openNotificationSettings() =>
      _open(platform.openNotificationSettings);

  /// Asks Android to stop battery saving for VoxScribe.
  Future<void> requestBatteryExemption() =>
      _open(platform.requestBatteryExemption);

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

  /// Does what the primary button says: the model download, the next permission step, or turns
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
      SetupStep.model => platform.downloadModel(),
      SetupStep.microphone => platform.requestMicrophone(),
      SetupStep.accessibility when appInfo => platform.openAppInfo(),
      SetupStep.accessibility => platform.openAccessibilitySettings(),
      SetupStep.overlay => platform.openOverlaySettings(),
      null => platform.setBubbleRunning(running: !_status.bubbleRunning),
    };
  }
}
