import 'package:flutter/services.dart';
import 'package:voxscribe_app/features/dictation/domain/dictation_engine.dart';

/// Records and transcribes with the native engine (`EngineChannel.kt`).
class MethodChannelDictationEngine implements DictationEngine {
  static const _method = MethodChannel('com.voxscribe.android/engine');
  static const _levels = EventChannel('com.voxscribe.android/engine/levels');

  @override
  Stream<double> get levels => _levels.receiveBroadcastStream().map(
    (level) => (level as num).toDouble(),
  );

  @override
  Future<void> start() => _guard(() => _method.invokeMethod<void>('start'));

  @override
  Future<DictationResult> stop() async {
    final raw = await _guard(
      () => _method.invokeMapMethod<String, Object?>('stop'),
    );
    final map = raw ?? const <String, Object?>{};
    return DictationResult(
      text: (map['text'] as String?) ?? '',
      duration: Duration(
        milliseconds: (map['durationMs'] as num?)?.toInt() ?? 0,
      ),
    );
  }

  @override
  Future<String> getLanguage() async {
    final code = await _guard(
      () => _method.invokeMethod<String>('getLanguage'),
    );
    return code ?? 'en';
  }

  @override
  Future<void> setLanguage(String code) {
    return _guard(
      () => _method.invokeMethod<void>('setLanguage', {'code': code}),
    );
  }

  Future<T> _guard<T>(Future<T> Function() call) async {
    try {
      return await call();
    } on PlatformException catch (error) {
      throw DictationException(error.message ?? 'Something went wrong.');
    }
  }
}
