import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/features/setup/domain/setup_status.dart';
import 'package:voxscribe_app/features/setup/setup_controller.dart';
import 'package:voxscribe_app/features/setup/widgets/restricted_steps.dart';

import 'support/fake_setup_platform.dart';
import 'support/test_app.dart';

const _newPhone = SetupStatus(
  microphone: false,
  accessibility: false,
  overlay: false,
  bubbleRunning: false,
  setupSeen: false,
  bubbleUsed: false,
);

const _readyNeverPressed = SetupStatus(
  microphone: true,
  accessibility: true,
  overlay: true,
  bubbleRunning: true,
  bubbleUsed: false,
);

Future<FakeSetupPlatform> _start(
  WidgetTester tester,
  SetupStatus status,
) async {
  tester.platformDispatcher.accessibilityFeaturesTestValue =
      const FakeAccessibilityFeatures(disableAnimations: true);
  addTearDown(tester.platformDispatcher.clearAccessibilityFeaturesTestValue);
  tester.view.physicalSize = const Size(800, 1800);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final platform = FakeSetupPlatform(status);
  await tester.pumpWidget(buildTestApp(setup: platform));
  await tester.pumpAndSettle();
  return platform;
}

void main() {
  group('SetupController first run and practice', () {
    test('a new install starts on the setup steps', () async {
      final controller = SetupController(
        platform: FakeSetupPlatform(_newPhone),
      );
      await controller.refresh();
      expect(controller.firstRun, isTrue);
      expect(controller.showReminder, isFalse);
    });

    test('the first run stays on after setup was opened once', () async {
      final platform = FakeSetupPlatform(_newPhone);
      final controller = SetupController(platform: platform);
      await controller.refresh();
      // The phone now remembers setup was seen, as after opened().
      platform.status = const SetupStatus(
        microphone: true,
        accessibility: false,
        overlay: false,
        bubbleRunning: false,
        bubbleUsed: false,
      );
      await controller.refresh();
      expect(controller.firstRun, isTrue);
    });

    test('an updated or set-up phone never gets the first run', () async {
      final seen = SetupController(
        platform: FakeSetupPlatform(SetupStatus.none),
      );
      await seen.refresh();
      expect(seen.firstRun, isFalse);
    });

    test('pressing the button in another app ends the first run', () async {
      final platform = FakeSetupPlatform(_newPhone);
      final controller = SetupController(platform: platform);
      await controller.refresh();
      platform.status = const SetupStatus(
        microphone: true,
        accessibility: true,
        overlay: true,
        bubbleRunning: true,
      );
      await controller.refresh();
      expect(controller.firstRun, isFalse);
    });

    test('practice shows once the button is on but never pressed', () async {
      final controller = SetupController(
        platform: FakeSetupPlatform(_readyNeverPressed),
      );
      await controller.refresh();
      expect(controller.showPractice, isTrue);
      controller.hidePractice();
      expect(controller.showPractice, isFalse);
    });

    test('no practice before the button is on', () async {
      final controller = SetupController(
        platform: FakeSetupPlatform(
          _readyNeverPressed.copyWith(bubbleRunning: false),
        ),
      );
      await controller.refresh();
      expect(controller.showPractice, isFalse);
    });
  });

  testWidgets(
    'a new install opens on the setup steps, Skip goes to Dictation',
    (tester) async {
      await _start(tester, _newPhone);
      expect(find.text('A few quick steps'), findsOneWidget);
      expect(find.text('Transcript'.toUpperCase()), findsNothing);

      await tester.tap(find.text('Skip for now'));
      await tester.pumpAndSettle();
      expect(find.text('A few quick steps'), findsNothing);
    },
  );

  testWidgets('a set-up phone opens on Dictation as before', (tester) async {
    await _start(tester, SetupStatus.none);
    expect(find.text('Skip for now'), findsNothing);
    expect(find.text('Dictate in any app'), findsOneWidget);
  });

  testWidgets('practice box: words arriving show It works, Done hides it', (
    tester,
  ) async {
    await _start(tester, _readyNeverPressed);
    expect(find.text('Try it here first'), findsOneWidget);

    await tester.enterText(
      find.byType(TextField).first,
      'Hello, this is my first try',
    );
    await tester.pumpAndSettle();
    expect(find.text('It works'), findsOneWidget);

    await tester.tap(find.text('Done'));
    await tester.pumpAndSettle();
    expect(find.text('Try it here first'), findsNothing);
    expect(find.text('It works'), findsNothing);
  });

  testWidgets('a restricted switch shows the numbered taps, App info marked '
      'after a failed try', (tester) async {
    tester.platformDispatcher.accessibilityFeaturesTestValue =
        const FakeAccessibilityFeatures(disableAnimations: true);
    addTearDown(tester.platformDispatcher.clearAccessibilityFeaturesTestValue);
    tester.view.physicalSize = const Size(800, 2000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    final platform = FakeSetupPlatform(
      const SetupStatus(
        microphone: true,
        accessibility: false,
        accessibilityRestricted: true,
        overlay: false,
        bubbleRunning: false,
      ),
    );
    await tester.pumpWidget(buildTestApp(setup: platform));
    await openTab(tester, 'Settings');
    await tester.tap(find.text('Speech model, button and permissions'));
    await tester.pumpAndSettle();

    final steps = tester.widget<RestrictedSteps>(find.byType(RestrictedSteps));
    expect(steps.current, 0);

    await tester.tap(find.text('Open accessibility settings'));
    await tester.pumpAndSettle();
    expect(
      tester.widget<RestrictedSteps>(find.byType(RestrictedSteps)).current,
      2,
    );
  });
}
