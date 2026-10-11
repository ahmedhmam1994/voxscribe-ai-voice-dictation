import 'package:flutter/services.dart';
import 'package:voxscribe_app/features/pro/domain/pro_repository.dart';

/// Talks to `ProChannel.kt`, which checks the key and claims it.
class MethodChannelProRepository implements ProRepository {
  static const _channel = MethodChannel('com.voxscribe.android/pro');

  @override
  Future<bool> isPro() async {
    try {
      return await _channel.invokeMethod<bool>('isPro') ?? false;
    } on PlatformException {
      return false;
    }
  }

  @override
  Future<ActivationResult> activate(String key) async {
    try {
      final raw = await _channel.invokeMapMethod<String, Object?>('activate', {
        'key': key,
      });
      return ActivationResult(
        ok: raw?['ok'] as bool? ?? false,
        message: raw?['message'] as String? ?? '',
      );
    } on PlatformException {
      return const ActivationResult(
        ok: false,
        message: 'Something went wrong. Try again.',
      );
    }
  }

  @override
  Future<void> deactivate() async {
    try {
      await _channel.invokeMethod<void>('deactivate');
    } on PlatformException {
      // Nothing to undo; the screen reads the state again afterwards.
    }
  }

  @override
  Future<void> openPurchasePage() async {
    try {
      await _channel.invokeMethod<void>('openPurchasePage');
    } on PlatformException {
      // No browser to open; the button simply does nothing.
    }
  }
}
