import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/scripted_engine.dart';
import 'support/test_app.dart';

void main() {
  testWidgets('shows the empty state before any dictation', (tester) async {
    await tester.pumpWidget(buildTestApp());

    expect(find.text('Ready'), findsOneWidget);
    expect(find.text('Hold to dictate'), findsOneWidget);
    expect(find.text('No dictations yet today.'), findsOneWidget);
    expect(find.textContaining('Your words appear here'), findsOneWidget);
  });

  testWidgets('hold, release, then the text and history appear', (
    tester,
  ) async {
    final engine = ScriptedEngine();
    await tester.pumpWidget(buildTestApp(engine: engine));

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
    expect(find.text('Floating button and permissions'), findsOneWidget);
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
}
