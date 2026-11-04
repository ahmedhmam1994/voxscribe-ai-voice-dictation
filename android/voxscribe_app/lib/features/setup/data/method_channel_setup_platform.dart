import 'package:flutter/services.dart';
import 'package:voxscribe_app/features/setup/domain/setup_platform.dart';
import 'package:voxscribe_app/features/setup/domain/setup_status.dart';

/// Talks to `SetupChannel.kt` on Android.
class MethodChannelSetupPlatform implements SetupPlatform {
  static const _channel = MethodChannel('com.voxscribe.android/setup');

  @override
  Future<SetupStatus> getStatus() async {
    final raw = await _channel.invokeMapMethod<String, bool>('getStatus');
    final map = raw ?? const <String, bool>{};
    final accessibilityOn = map['accessibility'] ?? false;
    final connected = map['accessibilityConnected'] ?? false;
    return SetupStatus(
      microphone: map['microphone'] ?? false,
      accessibility: accessibilityOn && connected,
      accessibilityNeedsRestart: accessibilityOn && !connected,
      // Only matters while the switch is still off.
      accessibilityRestricted:
          !accessibilityOn && (map['accessibilityRestricted'] ?? false),
      overlay: map['overlay'] ?? false,
      bubbleRunning: map['bubbleRunning'] ?? false,
      notifications: map['notifications'] ?? true,
    );
  }

  @override
  Future<void> requestMicrophone() => _invoke('requestMicrophone');

  @override
  Future<void> openAccessibilitySettings() =>
      _invoke('openAccessibilitySettings');

  @override
  Future<void> openAppInfo() => _invoke('openAppInfo');

  @override
  Future<void> openOverlaySettings() => _invoke('openOverlaySettings');

  @override
  Future<void> openNotificationSettings() =>
      _invoke('openNotificationSettings');

  @override
  Future<void> setupOpened() => _invoke('setupOpened');

  @override
  Future<QuickTileResult> addQuickTile() async {
    try {
      return switch (await _channel.invokeMethod<String>('addQuickTile')) {
        'added' => QuickTileResult.added,
        'already' => QuickTileResult.alreadyAdded,
        'declined' => QuickTileResult.declined,
        _ => QuickTileResult.manual,
      };
    } on PlatformException {
      return QuickTileResult.manual;
    } on MissingPluginException {
      return QuickTileResult.manual;
    }
  }

  @override
  Future<void> setBubbleRunning({required bool running}) {
    return _invoke('setBubbleRunning', {'running': running});
  }

  Future<void> _invoke(String method, [Map<String, Object?>? arguments]) async {
    try {
      await _channel.invokeMethod<void>(method, arguments);
    } on PlatformException catch (error) {
      throw SetupException(error.message ?? 'Something went wrong.');
    }
  }
}
