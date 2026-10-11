import 'package:voxscribe_app/features/settings/domain/app_settings.dart';
import 'package:voxscribe_app/features/settings/domain/settings_repository.dart';

/// Settings kept in memory. [saved] always holds what was last stored.
class FakeSettingsRepository implements SettingsRepository {
  FakeSettingsRepository([this.saved = AppSettings.defaults]);

  AppSettings saved;

  @override
  Future<AppSettings> load() async => saved;

  @override
  Future<void> setCleanup({required bool value}) async {
    saved = saved.copyWith(cleanup: value);
  }

  @override
  Future<void> setTrailingSpace({required bool value}) async {
    saved = saved.copyWith(trailingSpace: value);
  }

  @override
  Future<void> setTheme(ThemeChoice value) async {
    saved = saved.copyWith(theme: value);
  }
}
