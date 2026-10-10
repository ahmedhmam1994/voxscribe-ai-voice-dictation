import 'package:flutter/services.dart';
import 'package:voxscribe_app/features/history/domain/dictation_entry.dart';
import 'package:voxscribe_app/features/history/domain/history_repository.dart';

/// Talks to `HistoryChannel.kt`. A failure here never blocks dictation, so a
/// native error reads as "no history" and a failed save is skipped.
class MethodChannelHistoryRepository implements HistoryRepository {
  static const _channel = MethodChannel('com.voxscribe.android/history');

  @override
  Future<List<DictationEntry>> load() async {
    try {
      final raw = await _channel.invokeListMethod<Map<Object?, Object?>>(
        'getEntries',
      );
      return [for (final item in raw ?? const []) _fromMap(item)];
    } on PlatformException {
      return const [];
    }
  }

  @override
  Future<void> add(DictationEntry entry) async {
    try {
      await _channel.invokeMethod<void>('addEntry', {
        'text': entry.text,
        'at': entry.createdAt.millisecondsSinceEpoch,
        'ms': entry.duration.inMilliseconds,
      });
    } on PlatformException {
      // Not worth interrupting the user over.
    }
  }

  @override
  Future<void> clear() async {
    try {
      await _channel.invokeMethod<void>('clear');
    } on PlatformException {
      // The next load shows what is still there.
    }
  }

  DictationEntry _fromMap(Map<Object?, Object?> map) {
    return DictationEntry(
      text: map['text'] as String? ?? '',
      createdAt: DateTime.fromMillisecondsSinceEpoch(
        (map['at'] as num?)?.toInt() ?? 0,
      ),
      duration: Duration(milliseconds: (map['ms'] as num?)?.toInt() ?? 0),
    );
  }
}
