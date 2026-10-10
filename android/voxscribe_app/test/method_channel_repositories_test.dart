import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/features/history/data/method_channel_history_repository.dart';
import 'package:voxscribe_app/features/history/domain/dictation_entry.dart';
import 'package:voxscribe_app/features/settings/data/method_channel_settings_repository.dart';
import 'package:voxscribe_app/features/settings/domain/app_settings.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  final messenger =
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;

  group('history', () {
    const channel = MethodChannel('com.voxscribe.android/history');
    final repository = MethodChannelHistoryRepository();

    tearDown(() => messenger.setMockMethodCallHandler(channel, null));

    test('turns the native list into entries', () async {
      messenger.setMockMethodCallHandler(channel, (call) async {
        expect(call.method, 'getEntries');
        return [
          {'text': 'hello there', 'at': 1760000000000, 'ms': 2500},
        ];
      });

      final entries = await repository.load();

      expect(entries.single.text, 'hello there');
      expect(
        entries.single.createdAt,
        DateTime.fromMillisecondsSinceEpoch(1760000000000),
      );
      expect(entries.single.duration, const Duration(milliseconds: 2500));
    });

    test('sends a new entry with its time and duration', () async {
      MethodCall? received;
      messenger.setMockMethodCallHandler(channel, (call) async {
        received = call;
        return null;
      });

      await repository.add(
        DictationEntry(
          text: 'saved text',
          createdAt: DateTime.fromMillisecondsSinceEpoch(1760000000000),
          duration: const Duration(seconds: 3),
        ),
      );

      expect(received?.method, 'addEntry');
      expect(received?.arguments, {
        'text': 'saved text',
        'at': 1760000000000,
        'ms': 3000,
      });
    });

    test('a native error reads as no history', () async {
      messenger.setMockMethodCallHandler(channel, (call) async {
        throw PlatformException(code: 'broken');
      });

      expect(await repository.load(), isEmpty);
      await repository.clear();
    });
  });

  group('settings', () {
    const channel = MethodChannel('com.voxscribe.android/settings');
    final repository = MethodChannelSettingsRepository();

    tearDown(() => messenger.setMockMethodCallHandler(channel, null));

    test('reads the saved values', () async {
      messenger.setMockMethodCallHandler(channel, (call) async {
        return {'cleanup': false, 'trailingSpace': true, 'theme': 'dark'};
      });

      final settings = await repository.load();

      expect(settings.cleanup, isFalse);
      expect(settings.trailingSpace, isTrue);
      expect(settings.theme, ThemeChoice.dark);
    });

    test('an unknown theme falls back to the system theme', () async {
      messenger.setMockMethodCallHandler(channel, (call) async {
        return {'cleanup': true, 'trailingSpace': true, 'theme': 'purple'};
      });

      expect((await repository.load()).theme, ThemeChoice.system);
    });

    test('sends each change under its own method', () async {
      final calls = <MethodCall>[];
      messenger.setMockMethodCallHandler(channel, (call) async {
        calls.add(call);
        return null;
      });

      await repository.setCleanup(value: false);
      await repository.setTrailingSpace(value: false);
      await repository.setTheme(ThemeChoice.light);

      expect(calls.map((c) => c.method), [
        'setCleanup',
        'setTrailingSpace',
        'setTheme',
      ]);
      expect(calls.last.arguments, {'value': 'light'});
    });

    test('a native error gives the defaults', () async {
      messenger.setMockMethodCallHandler(channel, (call) async {
        throw PlatformException(code: 'broken');
      });

      expect(await repository.load(), AppSettings.defaults);
    });
  });
}
