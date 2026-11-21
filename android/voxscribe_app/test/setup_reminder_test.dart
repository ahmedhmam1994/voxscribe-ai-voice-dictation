import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/features/setup/domain/setup_status.dart';

import 'support/fake_setup_platform.dart';
import 'support/test_app.dart';

const _allGranted = SetupStatus(
  microphone: true,
  accessibility: true,
  overlay: true,
  bubbleRunning: false,
);

void main() {
  testWidgets('a new user is pointed to the setup steps', (tester) async {
    useTallScreen(tester);
    // The setup screen's looping demo never settles; show its still picture.
    tester.platformDispatcher.accessibilityFeaturesTestValue =
        const FakeAccessibilityFeatures(disableAnimations: true);
    addTearDown(tester.platformDispatcher.clearAccessibilityFeaturesTestValue);
    final setup = FakeSetupPlatform();
    await tester.pumpWidget(buildTestApp(setup: setup));
    await tester.pumpAndSettle();

    expect(find.text('Dictate in any app'), findsOneWidget);
    expect(find.text('0 of 4 done'), findsOneWidget);

    await tester.tap(find.text('Set up'));
    await tester.pumpAndSettle();

    expect(find.text('A few quick steps'), findsOneWidget);
    expect(setup.openedCount, 1);
  });

  testWidgets('with setup done the card turns the button on, then goes', (
    tester,
  ) async {
    useTallScreen(tester);
    final setup = FakeSetupPlatform(_allGranted);
    await tester.pumpWidget(buildTestApp(setup: setup));
    await tester.pumpAndSettle();

    expect(find.text('Turn on the floating button'), findsOneWidget);

    await tester.tap(find.text('Turn on'));
    await tester.pumpAndSettle();

    expect(setup.calls, ['setBubbleRunning:true']);
    expect(find.text('Turn on the floating button'), findsNothing);
  });

  testWidgets('an update with only the speech model missing downloads it '
      'and shows the progress', (tester) async {
    useTallScreen(tester);
    final setup = FakeSetupPlatform(
      const SetupStatus(
        microphone: true,
        accessibility: true,
        overlay: true,
        bubbleRunning: true,
        modelInstalled: false,
        modelMegabytes: 536,
      ),
    );
    await tester.pumpWidget(buildTestApp(setup: setup));
    await tester.pumpAndSettle();

    expect(find.text('Download the speech model'), findsOneWidget);
    await tester.tap(find.text('Download'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(setup.calls, ['downloadModel']);
    expect(find.text('Downloading the speech model'), findsOneWidget);
  });

  testWidgets('Not now hides the card', (tester) async {
    useTallScreen(tester);
    await tester.pumpWidget(buildTestApp());
    await tester.pumpAndSettle();

    await tester.tap(find.text('Not now'));
    await tester.pumpAndSettle();

    expect(find.text('Dictate in any app'), findsNothing);
  });

  testWidgets('no card once the button is on', (tester) async {
    useTallScreen(tester);
    final setup = FakeSetupPlatform(_allGranted.copyWith(bubbleRunning: true));
    await tester.pumpWidget(buildTestApp(setup: setup));
    await tester.pumpAndSettle();

    expect(find.text('Dictate in any app'), findsNothing);
    expect(find.text('Turn on the floating button'), findsNothing);
  });
}
