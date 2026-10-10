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

void main() {
  group('SetupStatus', () {
    test('steps come in order and the first missing one is next', () {
      expect(SetupStatus.none.nextStep, SetupStep.microphone);
      expect(_micOnly.nextStep, SetupStep.accessibility);
      expect(_allGranted.nextStep, isNull);
    });

    test('counts finished steps', () {
      expect(SetupStatus.none.doneCount, 0);
      expect(_micOnly.doneCount, 1);
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
      platform.status = _micOnly;
      await controller.refresh();
      await controller.performPrimaryAction();

      expect(platform.calls, [
        'requestMicrophone',
        'openAccessibilitySettings',
      ]);
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
  });
}
