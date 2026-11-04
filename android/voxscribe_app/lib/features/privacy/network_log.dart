import 'package:flutter/services.dart';

/// One time VoxScribe went online from this phone (see `NetworkLog.kt`).
class NetworkLogEntry {
  const NetworkLogEntry({
    required this.at,
    required this.what,
    required this.host,
    required this.sent,
  });

  final DateTime at;
  final String what;
  final String host;
  final String sent;
}

/// The privacy receipt's entries, newest first.
abstract interface class NetworkLog {
  Future<List<NetworkLogEntry>> entries();
}

/// Talks to `NetworkLogChannel.kt`. Empty when the native side is missing.
class MethodChannelNetworkLog implements NetworkLog {
  const MethodChannelNetworkLog();

  static const _channel = MethodChannel('com.voxscribe.android/networklog');

  @override
  Future<List<NetworkLogEntry>> entries() async {
    try {
      final raw = await _channel.invokeListMethod<Map<Object?, Object?>>(
        'entries',
      );
      return [
        for (final entry in raw ?? const <Map<Object?, Object?>>[])
          NetworkLogEntry(
            at: DateTime.fromMillisecondsSinceEpoch(entry['at'] as int? ?? 0),
            what: entry['what'] as String? ?? '',
            host: entry['host'] as String? ?? '',
            sent: entry['sent'] as String? ?? '',
          ),
      ];
    } on PlatformException {
      return const [];
    } on MissingPluginException {
      return const [];
    }
  }
}
