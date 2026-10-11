import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/features/dictation/dictation_controller.dart';
import 'package:voxscribe_app/features/dictation/domain/dictation_engine.dart';
import 'package:voxscribe_app/features/dictation/domain/dictation_status.dart';
import 'package:voxscribe_app/features/history/history_controller.dart';

import 'support/fake_history_repository.dart';
import 'support/scripted_engine.dart';

void main() {
  late ScriptedEngine engine;
  late HistoryController history;
  late DictationController controller;
  final clock = DateTime(2026, 10, 10, 9, 48);

  setUp(() {
    engine = ScriptedEngine();
    history = HistoryController(repository: FakeHistoryRepository());
    controller = DictationController(
      engine: engine,
      history: history,
      clock: () => clock,
    );
  });

  tearDown(() => controller.dispose());

  test('starts ready with nothing recorded', () {
    expect(controller.status, DictationStatus.ready);
    expect(controller.transcript, isNull);
    expect(history.entries, isEmpty);
  });

  test('holding records and keeps only the most recent levels', () async {
    await controller.holdStarted();
    expect(controller.status, DictationStatus.recording);

    for (var i = 0; i < DictationController.meterBars + 5; i++) {
      engine.emitLevel(i / 100);
      await Future<void>.delayed(Duration.zero);
    }

    expect(controller.recentLevels, hasLength(DictationController.meterBars));
    expect(controller.recentLevels.last, closeTo(0.18, 1e-9));
  });

  test('releasing transcribes and records a dictation', () async {
    await controller.holdStarted();
    final released = controller.holdReleased();
    await Future<void>.delayed(Duration.zero);
    expect(controller.status, DictationStatus.transcribing);

    engine.finish('  Remind me to call the dentist.  ');
    await released;

    expect(controller.status, DictationStatus.ready);
    expect(controller.transcript, 'Remind me to call the dentist.');
    expect(history.entries, hasLength(1));
    expect(history.entries.single.wordCount, 6);
    expect(history.entries.single.createdAt, clock);
  });

  test('newest dictation comes first', () async {
    for (final text in ['first one', 'second one']) {
      await controller.holdStarted();
      final released = controller.holdReleased();
      await Future<void>.delayed(Duration.zero);
      engine.finish(text);
      await released;
    }

    expect(history.entries.map((e) => e.text), ['second one', 'first one']);
  });

  test('empty transcript means no speech and adds nothing', () async {
    await controller.holdStarted();
    final released = controller.holdReleased();
    await Future<void>.delayed(Duration.zero);
    engine.finish('   ');
    await released;

    expect(controller.status, DictationStatus.noSpeech);
    expect(history.entries, isEmpty);
    expect(controller.canStart, isTrue);
  });

  test('a recording failure is reported and can be retried', () async {
    engine.startError = const DictationException('No microphone available.');
    await controller.holdStarted();

    expect(controller.status, DictationStatus.failed);
    expect(controller.errorMessage, 'No microphone available.');
    expect(controller.canStart, isTrue);

    engine.startError = null;
    await controller.holdStarted();
    expect(controller.status, DictationStatus.recording);
    expect(controller.errorMessage, isNull);
  });

  test('a transcription failure is reported', () async {
    await controller.holdStarted();
    final released = controller.holdReleased();
    await Future<void>.delayed(Duration.zero);
    engine.fail('The model is still loading.');
    await released;

    expect(controller.status, DictationStatus.failed);
    expect(controller.errorMessage, 'The model is still loading.');
  });

  test('cannot start again while transcribing', () async {
    await controller.holdStarted();
    final released = controller.holdReleased();
    await Future<void>.delayed(Duration.zero);

    await controller.holdStarted();
    expect(controller.status, DictationStatus.transcribing);

    engine.finish('done');
    await released;
  });

  test('releasing without recording does nothing', () async {
    await controller.holdReleased();

    expect(controller.status, DictationStatus.ready);
  });

  test('clearing removes the transcript but keeps the history', () async {
    await controller.holdStarted();
    final released = controller.holdReleased();
    await Future<void>.delayed(Duration.zero);
    engine.finish('keep me in history');
    await released;

    controller.clearTranscript();

    expect(controller.transcript, isNull);
    expect(history.entries, hasLength(1));
  });

  group('language', () {
    test('loads the language the engine uses', () async {
      engine.language = 'ar';

      await controller.loadLanguage();

      expect(controller.language, 'ar');
    });

    test('choosing a language switches the engine', () async {
      await controller.chooseLanguage('ar');

      expect(controller.language, 'ar');
      expect(engine.languageChanges, ['ar']);
      expect(controller.changingLanguage, isFalse);
    });

    test('choosing the current language does nothing', () async {
      await controller.chooseLanguage('en');

      expect(engine.languageChanges, isEmpty);
    });

    test('cannot switch while recording', () async {
      await controller.holdStarted();

      await controller.chooseLanguage('ar');

      expect(controller.language, 'en');
      expect(engine.languageChanges, isEmpty);
    });
  });
}
