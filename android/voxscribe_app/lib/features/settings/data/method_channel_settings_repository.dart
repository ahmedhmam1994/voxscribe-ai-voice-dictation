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
  Future<void> setTheme(ThemeChoice value) => _send('setTheme', value.name);

  Future<void> _send(String method, Object value) async {
    try {
      await _channel.invokeMethod<void>(method, {'value': value});
    } on PlatformException {
      // The screen already shows the new value; it just will not persist.
    }
  }

  ThemeChoice _themeFromName(String? name) {
    return ThemeChoice.values.firstWhere(
      (choice) => choice.name == name,
      orElse: () => ThemeChoice.system,
    );
  }
}
