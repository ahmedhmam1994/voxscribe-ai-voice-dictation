import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/features/setup/domain/setup_status.dart';

import 'support/fake_setup_platform.dart';
import 'support/test_app.dart';

Future<FakeSetupPlatform> _openSetup(
  WidgetTester tester,
  SetupStatus status,
) async {
  // The looping how-it-works demo never settles; these tests are about the
  // steps, so show it as its still picture.
  tester.platformDispatcher.accessibilityFeaturesTestValue =
      const FakeAccessibilityFeatures(disableAnimations: true);
  addTearDown(tester.platformDispatcher.clearAccessibilityFeaturesTestValue);
  // A taller screen than the default, so the steps below the demo are on screen.
  tester.view.physicalSize = const Size(800, 1600);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final platform = FakeSetupPlatform(status);
  await tester.pumpWidget(buildTestApp(setup: platform));
  await openTab(tester, 'Settings');
  await tester.tap(find.text('Speech model, button and permissions'));
  await tester.pumpAndSettle();
  return platform;
}

const _modelReady = SetupStatus(
  microphone: false,
  accessibility: false,
  overlay: false,
  bubbleRunning: false,
);

void main() {
  testWidgets('a fresh phone starts at the speech model', (tester) async {
    final platform = await _openSetup(
      tester,
      const SetupStatus(
        microphone: false,
        accessibility: false,
        overlay: false,
        bubbleRunning: false,
        modelInstalled: false,
        modelMegabytes: 536,
      ),
    );

    expect(find.text('A few quick steps'), findsOneWidget);
    expect(find.text('0 of 4 done'), findsOneWidget);
    expect(find.textContaining('VoxScribe types English'), findsOneWidget);
    await tester.tap(find.text('Download (536 MB)'));
    // The progress bar keeps moving until the download reports a percentage.
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(platform.calls, ['downloadModel']);
    expect(find.text('Allow microphone'), findsOneWidget);
    expect(find.text('Cancel download'), findsOneWidget);
  });

  testWidgets('the language can be changed before the download', (
    tester,
  ) async {
    final platform = await _openSetup(
      tester,
      const SetupStatus(
        microphone: false,
        accessibility: false,
        overlay: false,
        bubbleRunning: false,
        modelInstalled: false,
      ),
    );

    await tester.tap(find.text('Not English? Change the language'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Arabic'));
    await tester.pumpAndSettle();

    expect(platform.calls, ['setLanguage:ar']);
  });

  testWidgets('with the model there it starts at the microphone step', (
    tester,
  ) async {
    await _openSetup(tester, _modelReady);

    expect(find.text('1 of 4 done'), findsOneWidget);
    expect(find.text('Allow microphone'), findsOneWidget);
    expect(
      find.textContaining('only while you hold the button'),
      findsOneWidget,
    );
  });

  testWidgets('a disconnected accessibility service says to switch it off '
      'and on', (tester) async {
    await _openSetup(
      tester,
      const SetupStatus(
        microphone: true,
        accessibility: false,
        accessibilityNeedsRestart: true,
        overlay: true,
        bubbleRunning: false,
      ),
    );

    expect(find.textContaining('Android disconnected it'), findsOneWidget);
    expect(find.text('Open accessibility settings'), findsOneWidget);
  });

  testWidgets('finished steps show Done and the next one is explained', (
    tester,
  ) async {
    await _openSetup(
      tester,
      const SetupStatus(
        microphone: true,
        accessibility: false,
        overlay: false,
        bubbleRunning: false,
      ),
    );

    // The speech model and the microphone.
    expect(find.text('DONE'), findsNWidgets(2));
    expect(find.text('Open accessibility settings'), findsOneWidget);
    expect(find.textContaining('opens again by itself'), findsOneWidget);
  });

  testWidgets('a restricted switch warns before the user tries it', (
    tester,
  ) async {
    final platform = await _openSetup(
      tester,
      const SetupStatus(
        microphone: true,
        accessibility: false,
        accessibilityRestricted: true,
        overlay: false,
        bubbleRunning: false,
      ),
    );

    expect(find.textContaining('may say Restricted setting'), findsOneWidget);
    await tester.tap(find.text('Already saw it? Open App info'));
    await tester.pumpAndSettle();

    expect(platform.calls, ['openAppInfo']);
    expect(find.text('Open accessibility settings'), findsOneWidget);
  });

  testWidgets('back from a restricted switch still off, it sends the user to '
      'App info, then back to the switch', (tester) async {
    final platform = await _openSetup(
      tester,
      const SetupStatus(
        microphone: true,
        accessibility: false,
        accessibilityRestricted: true,
        overlay: false,
        bubbleRunning: false,
      ),
    );

    await tester.tap(find.text('Open accessibility settings'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Allow restricted settings'), findsOneWidget);

    await tester.tap(find.text('Open App info'));
    await tester.pumpAndSettle();
    expect(find.textContaining('may say Restricted setting'), findsOneWidget);
    expect(platform.calls, ['openAccessibilitySettings', 'openAppInfo']);
  });

  testWidgets('a phone installed from a store never mentions App info', (
    tester,
  ) async {
    await _openSetup(
      tester,
      const SetupStatus(
        microphone: true,
        accessibility: false,
        overlay: false,
        bubbleRunning: false,
      ),
    );

    await tester.tap(find.text('Open accessibility settings'));
    await tester.pumpAndSettle();

    expect(find.text('Open accessibility settings'), findsOneWidget);
    expect(find.textContaining('App info'), findsNothing);
  });

  testWidgets('the button runs the next step', (tester) async {
    final platform = await _openSetup(tester, _modelReady);

    await tester.tap(find.text('Allow microphone'));
    await tester.pumpAndSettle();

    expect(platform.calls, ['requestMicrophone']);
  });

  testWidgets('with everything granted it offers the floating button', (
    tester,
  ) async {
    final platform = await _openSetup(
      tester,
      const SetupStatus(
        microphone: true,
        accessibility: true,
        overlay: true,
        bubbleRunning: false,
      ),
    );

    expect(find.text('You are set'), findsOneWidget);
    await tester.tap(find.text('Show floating button'));
    await tester.pumpAndSettle();

    expect(platform.calls, ['setBubbleRunning:true']);
    expect(find.text('Turn off floating button'), findsOneWidget);
  });

  testWidgets('a failure is shown to the user', (tester) async {
    final platform = await _openSetup(tester, _modelReady);
    platform.failWith = 'Finish the setup steps first.';

    await tester.tap(find.text('Allow microphone'));
    await tester.pumpAndSettle();

    expect(find.text('Finish the setup steps first.'), findsOneWidget);
    expect(find.byType(Scrollable), findsWidgets);
  });

  testWidgets('says so when notifications are off and opens their settings', (
    tester,
  ) async {
    useTallScreen(tester);
    final platform = await _openSetup(
      tester,
      const SetupStatus(
        microphone: true,
        accessibility: true,
        overlay: true,
        bubbleRunning: true,
        notifications: false,
      ),
    );

    expect(find.text('Notifications are off'), findsOneWidget);
    await tester.ensureVisible(find.text('Open notification settings'));
    await tester.tap(find.text('Open notification settings'));
    await tester.pumpAndSettle();

    expect(platform.calls, contains('openNotificationSettings'));
  });

  testWidgets('shows no notice when notifications are on', (tester) async {
    useTallScreen(tester);
    await _openSetup(
      tester,
      const SetupStatus(
        microphone: true,
        accessibility: true,
        overlay: true,
        bubbleRunning: true,
      ),
    );

    expect(find.text('Notifications are off'), findsNothing);
  });

  testWidgets('asks to keep battery saving from closing the button', (
    tester,
  ) async {
    useTallScreen(tester);
    final platform = await _openSetup(
      tester,
      const SetupStatus(
        microphone: true,
        accessibility: true,
        overlay: true,
        bubbleRunning: true,
        batteryUnrestricted: false,
      ),
    );

    expect(find.text('Keep the button from disappearing'), findsOneWidget);
    expect(find.text('Open App info'), findsNothing);
    await tester.ensureVisible(find.text('Allow'));
    await tester.tap(find.text('Allow'));
    await tester.pumpAndSettle();
    expect(platform.calls, contains('requestBatteryExemption'));
  });

  testWidgets('on a Xiaomi phone it also points to App info', (tester) async {
    useTallScreen(tester);
    final platform = await _openSetup(
      tester,
      const SetupStatus(
        microphone: true,
        accessibility: true,
        overlay: true,
        bubbleRunning: true,
        batteryUnrestricted: false,
        xiaomi: true,
      ),
    );

    await tester.ensureVisible(find.text('Open App info'));
    await tester.tap(find.text('Open App info'));
    await tester.pumpAndSettle();
    expect(platform.calls, contains('openAppInfo'));
  });

  testWidgets('no battery card before the steps are done or once allowed', (
    tester,
  ) async {
    useTallScreen(tester);
    await _openSetup(
      tester,
      const SetupStatus(
        microphone: true,
        accessibility: false,
        overlay: false,
        bubbleRunning: false,
        batteryUnrestricted: false,
      ),
    );
    expect(find.text('Keep the button from disappearing'), findsNothing);
  });

  testWidgets('asks to allow running in background before the button', (
    tester,
  ) async {
    useTallScreen(tester);
    final platform = await _openSetup(
      tester,
      const SetupStatus(
        microphone: true,
        accessibility: true,
        overlay: true,
        bubbleRunning: false,
        batteryUnrestricted: false,
      ),
    );

    await tester.tap(find.text('Allow running in background'));
    await tester.pumpAndSettle();
    expect(platform.calls, contains('requestBatteryExemption'));
    // Asked once: if it was refused, the button can still be turned on.
    expect(find.text('Show floating button'), findsOneWidget);
  });

  testWidgets('Xiaomi tips open Autostart and go away on Done', (
    tester,
  ) async {
    useTallScreen(tester);
    final platform = await _openSetup(
      tester,
      const SetupStatus(
        microphone: true,
        accessibility: true,
        overlay: true,
        bubbleRunning: true,
        xiaomi: true,
        xiaomiTipsDone: false,
      ),
    );

    expect(
      find.text('On Xiaomi: stop the phone closing VoxScribe'),
      findsOneWidget,
    );
    await tester.ensureVisible(find.text('Open Autostart'));
    await tester.tap(find.text('Open Autostart'));
    await tester.pumpAndSettle();
    expect(platform.calls, contains('openAutostart'));
    await tester.ensureVisible(find.text('Done'));
    await tester.tap(find.text('Done'));
    await tester.pumpAndSettle();
    expect(platform.calls, contains('setXiaomiTipsDone'));
  });

  testWidgets('a disconnected typing service leads with Reconnect', (
    tester,
  ) async {
    useTallScreen(tester);
    await tester.pumpWidget(
      buildTestApp(
        setup: FakeSetupPlatform(
          const SetupStatus(
            microphone: true,
            accessibility: false,
            accessibilityNeedsRestart: true,
            overlay: true,
            bubbleRunning: false,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Reconnect VoxScribe'), findsOneWidget);
    expect(find.textContaining('turn it off, then on again'), findsOneWidget);
  });
}
