import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:voxscribe_app/features/setup/domain/setup_status.dart';

import 'support/fake_setup_platform.dart';
import 'support/scripted_engine.dart';
import 'support/test_app.dart';

/// Permissions not granted yet, but the speech model is on the phone.
const _modelReady = SetupStatus(
  microphone: false,
  accessibility: false,
  overlay: false,
  bubbleRunning: false,
);

void main() {
  testWidgets('shows the empty state before any dictation', (tester) async {
    await tester.pumpWidget(
      buildTestApp(setup: FakeSetupPlatform(_modelReady)),
    );

    expect(find.text('Ready'), findsOneWidget);
    expect(find.text('Hold to dictate'), findsOneWidget);
    expect(find.text('No dictations yet today.'), findsOneWidget);
    expect(
      find.textContaining('Hold the green button and talk'),
      findsOneWidget,
    );
  });

  testWidgets('hold, release, then the text and history appear', (
    tester,
  ) async {
    final engine = ScriptedEngine();
    await tester.pumpWidget(
      buildTestApp(engine: engine, setup: FakeSetupPlatform(_modelReady)),
    );

    final gesture = await tester.startGesture(
      tester.getCenter(find.text('Hold to dictate')),
    );
    await tester.pump();
    expect(find.text('Listening'), findsOneWidget);
    expect(find.text('Release to type'), findsWidgets);

    await gesture.up();
    await tester.pump();
    expect(find.text('Transcribing'), findsOneWidget);

    engine.finish('Pick up the parcel from the neighbour.');
    await tester.pump();
    await tester.pumpAndSettle();

    expect(find.text('Ready'), findsOneWidget);
    // Once in the transcript card and once in today's list.
    expect(
      find.textContaining('Pick up the parcel', findRichText: true),
      findsWidgets,
    );
    expect(find.text('No dictations yet today.'), findsNothing);
  });

  testWidgets('copy and clear are disabled until there is a transcript', (
    tester,
  ) async {
    await tester.pumpWidget(buildTestApp());

    final copy = tester.widget<ButtonStyleButton>(
      find.ancestor(
        of: find.text('Copy'),
        matching: find.bySubtype<ButtonStyleButton>(),
      ),
    );
    expect(copy.onPressed, isNull);
  });

  testWidgets('the other sections are reachable from the bottom bar', (
    tester,
  ) async {
    await tester.pumpWidget(buildTestApp());

    await openTab(tester, 'Insights');
    expect(find.textContaining('Counted on this phone only'), findsOneWidget);

    await openTab(tester, 'Settings');
    expect(find.text('Speech model, button and permissions'), findsOneWidget);
  });

  testWidgets('the language chip shows English and switches to Arabic', (
    tester,
  ) async {
    final engine = ScriptedEngine();
    await tester.pumpWidget(buildTestApp(engine: engine));
    await tester.pumpAndSettle();
    expect(find.text('English'), findsOneWidget);

    await tester.tap(find.text('English'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Arabic'));
    await tester.pumpAndSettle();

    expect(engine.languageChanges, ['ar']);
    expect(find.text('Arabic'), findsOneWidget);
  });

  testWidgets('the pill says when the speech model is missing', (tester) async {
    await tester.pumpWidget(buildTestApp());
    await tester.pump();
    expect(find.text('Speech model needed'), findsOneWidget);
    expect(find.text('Ready'), findsNothing);
  });

  testWidgets('Download in the language offer stays on the Dictation tab', (
    tester,
  ) async {
    final setup = FakeSetupPlatform();
    await tester.pumpWidget(buildTestApp(setup: setup));
    await tester.pumpAndSettle();
    await tester.tap(find.text('English'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Arabic'));
    await tester.pumpAndSettle();

    expect(find.textContaining('model'), findsWidgets);
    expect(find.widgetWithText(FilledButton, 'Download'), findsWidgets);
    await tester.tap(find.widgetWithText(FilledButton, 'Download').last);
    await tester.pump(const Duration(milliseconds: 500));

    expect(setup.calls, contains('downloadModel'));
    expect(find.text('Hold to dictate'), findsOneWidget);
    expect(find.text('Language you speak'), findsNothing);
  });
}
