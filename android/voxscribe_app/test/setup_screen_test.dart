import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/features/setup/domain/setup_status.dart';

import 'support/fake_setup_platform.dart';
import 'support/test_app.dart';

Future<FakeSetupPlatform> _openSetup(
  WidgetTester tester,
  SetupStatus status,
) async {
  final platform = FakeSetupPlatform(status);
  await tester.pumpWidget(buildTestApp(setup: platform));
  await openTab(tester, 'Settings');
  await tester.tap(find.text('Floating button and permissions'));
  await tester.pumpAndSettle();
  return platform;
}

void main() {
  testWidgets('a fresh phone starts at the microphone step', (tester) async {
    await _openSetup(tester, SetupStatus.none);

    expect(find.text('Three quick steps'), findsOneWidget);
    expect(find.text('0 of 3 done'), findsOneWidget);
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

    expect(find.text('DONE'), findsOneWidget);
    expect(find.text('Open accessibility settings'), findsOneWidget);
    expect(find.textContaining('tap VoxScribe and turn it on'), findsOneWidget);
  });

  testWidgets('the button runs the next step', (tester) async {
    final platform = await _openSetup(tester, SetupStatus.none);

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
    final platform = await _openSetup(tester, SetupStatus.none);
    platform.failWith = 'Finish the setup steps first.';

    await tester.tap(find.text('Allow microphone'));
    await tester.pumpAndSettle();

    expect(find.text('Finish the setup steps first.'), findsOneWidget);
    expect(find.byType(Scrollable), findsWidgets);
  });
}
