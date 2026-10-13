import 'dart:convert';
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:voxscribe_app/features/release/domain/release.dart';
import 'package:voxscribe_app/features/release/domain/release_repository.dart';

/// Talks to `ReleaseChannel.kt` for what is saved on the phone and reads the
/// project's public GitHub release list for new versions. Nothing about the
/// user is sent: it is one anonymous GET.
class MethodChannelReleaseRepository implements ReleaseRepository {
  static const _channel = MethodChannel('com.voxscribe.android/release');
  static final _releasesUrl = Uri.parse(
    'https://api.github.com/repos/ahmedhmam1994/voxscribe-ai-voice-dictation/releases?per_page=30',
  );

  @override
  Future<ReleaseState> state() async {
    try {
      final raw = await _channel.invokeMapMethod<String, Object?>('getState');
      return ReleaseState(
        version: raw?['version'] as String? ?? '0.0.0',
        lastSeen: raw?['lastSeen'] as String?,
        dismissedUpdate: raw?['dismissedUpdate'] as String?,
      );
    } on PlatformException {
      return const ReleaseState(version: '0.0.0');
    }
  }

  @override
  Future<void> markSeen(String version) async {
    try {
      await _channel.invokeMethod<void>('markSeen', {'version': version});
    } on PlatformException {
      // Showing the notes once more is harmless.
    }
  }

  @override
  Future<void> dismissUpdate(String version) async {
    try {
      await _channel.invokeMethod<void>('dismissUpdate', {'version': version});
    } on PlatformException {
      // The banner simply shows again next launch.
    }
  }

  @override
  Future<ReleaseInfo?> fetchLatest() async {
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 6);
    try {
      final request = await client.getUrl(_releasesUrl);
      request.headers.set('Accept', 'application/vnd.github+json');
      final response = await request.close().timeout(
        const Duration(seconds: 8),
      );
      if (response.statusCode != 200) return null;
      final body = await response.transform(utf8.decoder).join();
      return parseLatestAndroidRelease(body);
    } on Exception {
      return null;
    } finally {
      client.close(force: true);
    }
  }

  @override
  Future<void> open(String url) async {
    try {
      await _channel.invokeMethod<bool>('openUrl', {'url': url});
    } on PlatformException {
      // Nothing to fall back to; the user can open the releases page by hand.
    }
  }
}
