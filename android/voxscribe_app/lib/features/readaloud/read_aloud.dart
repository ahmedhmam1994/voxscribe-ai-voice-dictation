import 'package:flutter/services.dart';

/// Reads text aloud with the phone's own voice (see `ReadAloud.kt`).
abstract interface class ReadAloud {
  Future<void> speak(String text);

  Future<void> stop();
}

/// Talks to `ReadAloudChannel.kt`. Does nothing when the native side is missing.
class MethodChannelReadAloud implements ReadAloud {
  const MethodChannelReadAloud();

  static const _channel = MethodChannel('com.voxscribe.android/readaloud');

  @override
  Future<void> speak(String text) => _call('speak', {'text': text});

  @override
  Future<void> stop() => _call('stop');

  Future<void> _call(String method, [Map<String, Object?>? arguments]) async {
    try {
      await _channel.invokeMethod<void>(method, arguments);
    } on PlatformException {
      // No voice on this phone: nothing to read with.
    } on MissingPluginException {
      // Tests and previews.
    }
  }
}
