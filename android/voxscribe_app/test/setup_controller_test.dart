import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/features/setup/domain/setup_status.dart';
import 'package:voxscribe_app/features/setup/setup_controller.dart';

import 'support/fake_setup_platform.dart';

const _micOnly = SetupStatus(
  microphone: true,
  accessibility: false,
  overlay: false,
  bubbleRunning: false,
);

const _allGranted = SetupStatus(
  microphone: true,
  accessibility: true,
  overlay: true,
  bubbleRunning: false,
);

const _modelOnly = SetupStatus(
  microphone: false,
  accessibility: false,
  overlay: false,
  bubbleRunning: false,
);

void main() {
  group('SetupStatus', () {
    test('steps come in order and the first missing one is next', () {
      expect(SetupStatus.none.nextStep, SetupStep.model);
      expect(_modelOnly.nextStep, SetupStep.microphone);
      expect(_micOnly.nextStep, SetupStep.accessibility);
      expect(_allGranted.nextStep, isNull);
    });

    test('counts finished steps', () {
      expect(SetupStatus.none.doneCount, 0);
      expect(_modelOnly.doneCount, 1);
      expect(_micOnly.doneCount, 2);
      expect(_allGranted.doneCount, SetupStep.values.length);
      expect(_allGranted.permissionsComplete, isTrue);
    });
  });

  group('SetupController', () {
    test('refresh reads the phone state', () async {
      final platform = FakeSetupPlatform(_micOnly);
      final controller = SetupController(platform: platform);

      await controller.refresh();

      expect(controller.status, _micOnly);
    });

    test('the primary action does the next missing step', () async {
      final platform = FakeSetupPlatform();
      final controller = SetupController(platform: platform);
      await controller.refresh();

      await controller.performPrimaryAction();
      // The download runs on: the next step is the microphone meanwhile.
      expect(controller.status.nextStep, SetupStep.microphone);
      await controller.performPrimaryAction();
      platform.status = _micOnly;
      await controller.refresh();
      await controller.performPrimaryAction();

      expect(platform.calls, [
        'downloadModel',
        'requestMicrophone',
        'openAccessibilitySettings',
      ]);
      controller.dispose();
    });

    test('a language change is saved and reported', () async {
      final platform = FakeSetupPlatform(_modelOnly);
      var changed = 0;
      final controller = SetupController(
        platform: platform,
        onLanguageChanged: () => changed++,
      );
      await controller.refresh();

      await controller.chooseLanguage('ar');
      await controller.chooseLanguage('en'); // the language it already has

      expect(platform.calls, ['setLanguage:ar']);
      expect(changed, 1);
    });

    test('the reminder stays while the model downloads', () async {
      final platform = FakeSetupPlatform(
        const SetupStatus(
          microphone: true,
          accessibility: true,
          overlay: true,
          bubbleRunning: true,
          modelInstalled: false,
          modelDownloading: true,
          modelPercent: 40,
        ),
      );
      final controller = SetupController(platform: platform);
      await controller.refresh();

      expect(controller.status.permissionsComplete, isTrue);
      expect(controller.showReminder, isTrue);
      controller.dispose();
    });

    test('opens the overlay settings once the first two are done', () async {
      final platform = FakeSetupPlatform(
        const SetupStatus(
          microphone: true,
          accessibility: true,
          overlay: false,
          bubbleRunning: false,
        ),
      );
      final controller = SetupController(platform: platform);
      await controller.refresh();

      await controller.performPrimaryAction();

      expect(platform.calls, ['openOverlaySettings']);
    });

    test(
      'with everything granted the action toggles the floating button',
      () async {
        final platform = FakeSetupPlatform(_allGranted);
        final controller = SetupController(platform: platform);
        await controller.refresh();

        await controller.performPrimaryAction();
        expect(controller.status.bubbleRunning, isTrue);

        await controller.performPrimaryAction();
        expect(controller.status.bubbleRunning, isFalse);
        expect(platform.calls, [
          'setBubbleRunning:true',
          'setBubbleRunning:false',
        ]);
      },
    );

    test('a failed action is reported and does not stick', () async {
      final platform = FakeSetupPlatform(_allGranted)
        ..failWith = 'Finish the setup steps first.';
      final controller = SetupController(platform: platform);
      await controller.refresh();

      await controller.performPrimaryAction();
      expect(controller.errorMessage, 'Finish the setup steps first.');
      expect(controller.busy, isFalse);

      await controller.performPrimaryAction();
      expect(controller.errorMessage, isNull);
    });

    test('the reminder waits for the real state, then shows until the '
        'button is on', () async {
      final platform = FakeSetupPlatform(_micOnly);
      final controller = SetupController(platform: platform);
      expect(controller.showReminder, isFalse);

      await controller.refresh();
      expect(controller.showReminder, isTrue);

      platform.status = _allGranted;
      await controller.refresh();
      expect(controller.showReminder, isTrue);

      platform.status = _allGranted.copyWith(bubbleRunning: true);
      await controller.refresh();
      expect(controller.showReminder, isFalse);
    });

    test('Not now hides the reminder', () async {
      final controller = SetupController(platform: FakeSetupPlatform());
      await controller.refresh();

      controller.hideReminder();

      expect(controller.showReminder, isFalse);
    });

    test('opening the setup screen is reported to the platform', () async {
      final platform = FakeSetupPlatform();
      await SetupController(platform: platform).opened();

      expect(platform.openedCount, 1);
      expect(platform.calls, isEmpty);
    });
  });
}
