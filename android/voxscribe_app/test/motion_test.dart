import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/app/theme/app_theme.dart';
import 'package:voxscribe_app/features/dictation/widgets/level_meter.dart';
import 'package:voxscribe_app/features/dictation/widgets/typing_text.dart';
import 'package:voxscribe_app/features/dictation/widgets/voice_waveform.dart';
import 'package:voxscribe_app/features/insights/widgets/week_bars.dart';

import 'support/scripted_engine.dart';
import 'support/test_app.dart';

void main() {
  group('WeekBars blocks', () {
    test('a block is the smallest unit that fits the busiest day', () {
      expect(WeekBars.unitFor([0, 0]), 10);
      expect(WeekBars.unitFor([0, 116]), 10);
      expect(WeekBars.unitFor([0, 280]), 25);
      expect(WeekBars.unitFor([0, 500]), 50);
      expect(WeekBars.unitFor([0, 300, 1200]), 100);
      expect(WeekBars.unitFor([0, 1300]), 200);
      expect(WeekBars.unitFor([5000]), 500);
    });

    test('any dictation gets a block, and no day overflows', () {
      expect(WeekBars.blocksFor(0, 100), 0);
      expect(WeekBars.blocksFor(12, 100), 1);
      expect(WeekBars.blocksFor(460, 100), 5);
      expect(WeekBars.blocksFor(5000, 100), WeekBars.maxBlocks);
    });
  });

  testWidgets('recording shows the live waveform and level, then the words '
      'land in the card', (tester) async {
    final engine = ScriptedEngine();
    await tester.pumpWidget(buildTestApp(engine: engine));

    final gesture = await tester.startGesture(
      tester.getCenter(find.text('Hold to dictate')),
    );
    await tester.pump();
    engine
      ..emitLevel(0.4)
      ..emitLevel(0.9);
    await tester.pump();

    expect(find.byType(VoiceWaveform), findsOneWidget);
    expect(find.textContaining('Hold the green button and talk'), findsNothing);
    // One meter in the status pill, one in the button.
    expect(find.byType(LevelMeter), findsNWidgets(2));

    await gesture.up();
    await tester.pump();
    engine.finish('Move the meeting to three thirty.');
    await tester.pumpAndSettle();

    expect(find.byType(VoiceWaveform), findsNothing);
    expect(find.byType(TypingText), findsOneWidget);
    expect(
      find.textContaining(
        'Move the meeting to three thirty.',
        findRichText: true,
      ),
      findsWidgets,
    );
  });

  testWidgets('typed words keep their place while they land', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.dark,
        home: const Scaffold(body: TypingText('one two three')),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 60));

    // Mid-way the full sentence is already laid out, the rest just invisible.
    final rich = tester.widget<RichText>(find.byType(RichText).first);
    expect(rich.text.toPlainText(), contains('three'));

    await tester.pumpAndSettle();
    expect(find.text('one two three', findRichText: true), findsOneWidget);
  });
}
