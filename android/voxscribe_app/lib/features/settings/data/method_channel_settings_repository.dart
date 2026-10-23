import 'package:flutter/services.dart';
import 'package:voxscribe_app/features/settings/domain/app_settings.dart';
import 'package:voxscribe_app/features/settings/domain/settings_repository.dart';

/// Talks to `SettingsChannel.kt`. If the native side cannot be reached, the
/// defaults are used and changes simply are not saved.
class MethodChannelSettingsRepository implements SettingsRepository {
  static const _channel = MethodChannel('com.voxscribe.android/settings');

  @override
  Future<AppSettings> load() async {
    try {
      final raw = await _channel.invokeMapMethod<String, Object?>(
        'getSettings',
      );
      if (raw == null) return AppSettings.defaults;
      return AppSettings(
        cleanup: raw['cleanup'] as bool? ?? AppSettings.defaults.cleanup,
        trailingSpace:
            raw['trailingSpace'] as bool? ?? AppSettings.defaults.trailingSpace,
        theme: _themeFromName(raw['theme'] as String?),
        usagePing: raw['usagePing'] as bool? ?? AppSettings.defaults.usagePing,
        recordingMode: _byName(RecordingMode.values, raw['recordingMode'], RecordingMode.both),
        bubbleSize: _byName(BubbleSize.values, raw['bubbleSize'], BubbleSize.medium),
      );
    } on PlatformException {
      return AppSettings.defaults;
    }
  }

  @override
  Future<void> setCleanup({required bool value}) => _send('setCleanup', value);

  @override
  Future<void> setTrailingSpace({required bool value}) =>
      _send('setTrailingSpace', value);

  @override
  Future<void> setUsagePing({required bool value}) =>
      _send('setUsagePing', value);

  @override
  Future<void> setTheme(ThemeChoice value) => _send('setTheme', value.name);

  @override
  Future<void> setRecordingMode(RecordingMode value) =>
      _send('setRecordingMode', value.name);

  @override
  Future<void> setBubbleSize(BubbleSize value) =>
      _send('setBubbleSize', value.name);

  Future<void> _send(String method, Object value) async {
    try {
      await _channel.invokeMethod<void>(method, {'value': value});
    } on PlatformException {
      // The screen already shows the new value; it just will not persist.
    }
  }

  /// The saved name back to its value; anything unknown is [fallback].
  T _byName<T extends Enum>(List<T> values, Object? name, T fallback) {
    for (final value in values) {
      if (value.name == name) return value;
    }
    return fallback;
  }

  ThemeChoice _themeFromName(String? name) {
    return ThemeChoice.values.firstWhere(
      (choice) => choice.name == name,
      orElse: () => ThemeChoice.system,
    );
  }
}
