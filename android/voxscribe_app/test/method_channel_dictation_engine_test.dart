import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/features/dictation/data/method_channel_dictation_engine.dart';
import 'package:voxscribe_app/features/dictation/domain/dictation_engine.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const channel = MethodChannel('com.voxscribe.android/engine');
  final messenger =
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
  final engine = MethodChannelDictationEngine();

  void answerWith(Future<Object?>? Function(MethodCall call) handler) {
    messenger.setMockMethodCallHandler(channel, handler);
  }

  tearDown(() => messenger.setMockMethodCallHandler(channel, null));

  test('start calls the native start method', () async {
    final calls = <String>[];
    answerWith((call) async {
      calls.add(call.method);
      return null;
    });

    await engine.start();

    expect(calls, ['start']);
  });

  test('stop turns the native answer into a result', () async {
    answerWith(
      (call) async => {
        'text': 'Remind me to call the dentist.',
        'durationMs': 2400,
      },
    );

    final result = await engine.stop();

    expect(result.text, 'Remind me to call the dentist.');
    expect(result.duration, const Duration(milliseconds: 2400));
  });

  test('an empty native answer means no speech', () async {
    answerWith((call) async => {'text': '', 'durationMs': 800});

    final result = await engine.stop();

    expect(result.text, isEmpty);
  });

  test('a native error becomes a readable exception', () async {
    answerWith((call) async {
      throw PlatformException(
        code: 'no_microphone',
        message: 'Allow the microphone in Setup first.',
      );
    });

    await expectLater(
      engine.start(),
      throwsA(
        isA<DictationException>().having(
          (e) => e.message,
          'message',
          'Allow the microphone in Setup first.',
        ),
      ),
    );
  });
}
