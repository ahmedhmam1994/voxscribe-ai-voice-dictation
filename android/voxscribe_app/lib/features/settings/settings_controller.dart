import 'package:flutter/foundation.dart';
import 'package:voxscribe_app/features/settings/domain/app_settings.dart';
import 'package:voxscribe_app/features/settings/domain/settings_repository.dart';

/// Holds the saved settings. A change shows immediately and is then saved.
class SettingsController extends ChangeNotifier {
  SettingsController({required this.repository});

  final SettingsRepository repository;

  AppSettings _settings = AppSettings.defaults;

  AppSettings get settings => _settings;

  Future<void> load() async {
    _settings = await repository.load();
    notifyListeners();
  }

  Future<void> setCleanup({required bool value}) {
    _settings = _settings.copyWith(cleanup: value);
    notifyListeners();
    return repository.setCleanup(value: value);
  }

  Future<void> setTrailingSpace({required bool value}) {
    _settings = _settings.copyWith(trailingSpace: value);
    notifyListeners();
    return repository.setTrailingSpace(value: value);
  }

  Future<void> setTheme(ThemeChoice value) {
    _settings = _settings.copyWith(theme: value);
    notifyListeners();
    return repository.setTheme(value);
  }
}
