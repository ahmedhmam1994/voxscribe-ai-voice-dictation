import 'package:flutter/services.dart';
import 'package:voxscribe_app/features/setup/domain/setup_platform.dart';
import 'package:voxscribe_app/features/setup/domain/setup_status.dart';

/// Talks to `SetupChannel.kt` on Android.
class MethodChannelSetupPlatform implements SetupPlatform {
  static const _channel = MethodChannel('com.voxscribe.android/setup');

  @override
  Future<SetupStatus> getStatus() async {
    final raw = await _channel.invokeMapMethod<String, Object?>('getStatus');
    final values = raw ?? const <String, Object?>{};
    final map = {
      for (final MapEntry(:key, :value) in values.entries)
        if (value is bool) key: value,
    };
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
      setupSeen: map['setupSeen'] ?? true,
      bubbleUsed: map['bubbleUsed'] ?? true,
      batteryUnrestricted: map['batteryUnrestricted'] ?? true,
      xiaomi: map['xiaomi'] ?? false,
      xiaomiTipsDone: map['xiaomiTipsDone'] ?? true,
      language: values['language'] as String? ?? 'en',
      modelInstalled: map['modelInstalled'] ?? false,
      modelDownloading: map['modelDownloading'] ?? false,
      modelPercent: (values['modelPercent'] as num?)?.toInt() ?? 0,
      modelMegabytes: (values['modelMegabytes'] as num?)?.toInt() ?? 0,
      modelError: values['modelError'] as String?,
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
  Future<void> requestBatteryExemption() => _invoke('requestBatteryExemption');

  @override
  Future<void> openAutostart() => _invoke('openAutostart');

  @override
  Future<void> setXiaomiTipsDone() => _invoke('setXiaomiTipsDone');

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
  Future<void> downloadModel() => _invoke('downloadModel');

  @override
  Future<void> cancelModel() => _invoke('cancelModel');

  @override
  Future<void> setLanguage(String code) =>
      _invoke('setLanguage', {'code': code});

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
