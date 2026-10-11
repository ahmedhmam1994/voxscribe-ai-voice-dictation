import 'package:flutter/services.dart';
import 'package:voxscribe_app/features/snippets/domain/snippet.dart';
import 'package:voxscribe_app/features/snippets/domain/snippet_repository.dart';

/// Talks to `ProChannel.kt`. If the native side cannot be reached the list is
/// empty and changes are not saved.
class MethodChannelSnippetRepository implements SnippetRepository {
  static const _channel = MethodChannel('com.voxscribe.android/pro');

  @override
  Future<List<Snippet>> load() async {
    try {
      final raw = await _channel.invokeListMethod<Map<Object?, Object?>>(
        'getSnippets',
      );
      return [
        for (final item in raw ?? const <Map<Object?, Object?>>[])
          Snippet(
            trigger: item['trigger'] as String? ?? '',
            expansion: item['expansion'] as String? ?? '',
          ),
      ];
    } on PlatformException {
      return const [];
    }
  }

  @override
  Future<void> save(List<Snippet> snippets) async {
    try {
      await _channel.invokeMethod<void>('setSnippets', {
        'snippets': [
          for (final snippet in snippets)
            {'trigger': snippet.trigger, 'expansion': snippet.expansion},
        ],
      });
    } on PlatformException {
      // The list on screen is right; it just will not persist.
    }
  }
}
