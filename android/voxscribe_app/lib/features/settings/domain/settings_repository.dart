import 'package:voxscribe_app/features/settings/domain/app_settings.dart';

/// Where the user's settings are saved. The native services read the same
/// values, so a change applies to the floating button too.
abstract interface class SettingsRepository {
  Future<AppSettings> load();

  Future<void> setCleanup({required bool value});

  Future<void> setTrailingSpace({required bool value});

  Future<void> setTheme(ThemeChoice value);
}
