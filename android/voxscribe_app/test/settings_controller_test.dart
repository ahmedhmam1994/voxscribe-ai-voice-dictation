import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/features/settings/domain/app_settings.dart';
import 'package:voxscribe_app/features/settings/settings_controller.dart';

import 'support/fake_settings_repository.dart';

void main() {
  test('starts with the defaults', () {
    final controller = SettingsController(repository: FakeSettingsRepository());

    expect(controller.settings, AppSettings.defaults);
  });

  test('loads what was saved', () async {
    final repository = FakeSettingsRepository(
      const AppSettings(
        cleanup: false,
        trailingSpace: false,
        theme: ThemeChoice.dark,
      ),
    );
    final controller = SettingsController(repository: repository);

    await controller.load();

    expect(controller.settings.cleanup, isFalse);
    expect(controller.settings.theme, ThemeChoice.dark);
  });

  test('a change shows at once and is saved', () async {
    final repository = FakeSettingsRepository();
    final controller = SettingsController(repository: repository);

    final saving = controller.setCleanup(value: false);
    expect(controller.settings.cleanup, isFalse);
    await saving;

    expect(repository.saved.cleanup, isFalse);
  });

  test('each setting is saved on its own', () async {
    final repository = FakeSettingsRepository();
    final controller = SettingsController(repository: repository);

    await controller.setTrailingSpace(value: false);
    await controller.setTheme(ThemeChoice.light);

    expect(repository.saved.trailingSpace, isFalse);
    expect(repository.saved.theme, ThemeChoice.light);
    expect(repository.saved.cleanup, isTrue);
  });

  test('listeners hear about changes', () async {
    final controller = SettingsController(repository: FakeSettingsRepository());
    var notifications = 0;
    controller.addListener(() => notifications++);

    await controller.setTheme(ThemeChoice.dark);

    expect(notifications, 1);
  });
}
