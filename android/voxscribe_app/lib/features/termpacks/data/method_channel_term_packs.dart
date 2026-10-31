import 'package:flutter/services.dart';
import 'package:voxscribe_app/features/termpacks/domain/term_packs.dart';

/// Talks to `TermPacksChannel.kt`. If the native side cannot be reached there
/// are simply no packs.
class MethodChannelTermPacks implements TermPacksPlatform {
  static const _channel = MethodChannel('com.voxscribe.android/termpacks');

  @override
  Future<List<TermPack>> list() async {
    try {
      final raw = await _channel.invokeListMethod<Map<Object?, Object?>>(
        'listPacks',
      );
      return (raw ?? const []).map(_pack).toList();
    } on PlatformException {
      return const [];
    } on MissingPluginException {
      return const [];
    }
  }

  @override
  Future<TermPack> import(String fileName, String text) async {
    try {
      final raw = await _channel.invokeMapMethod<Object?, Object?>(
        'importPack',
        {'fileName': fileName, 'text': text},
      );
      if (raw == null) {
        throw const TermPackException('Could not save the pack.');
      }
      return _pack(raw);
    } on PlatformException catch (e) {
      throw TermPackException(e.message ?? 'Could not save the pack.');
    } on MissingPluginException {
      throw const TermPackException('Could not save the pack.');
    }
  }

  @override
  Future<void> remove(String id) async {
    try {
      await _channel.invokeMethod<bool>('removePack', {'id': id});
    } on PlatformException {
      // Still listed; the next load shows it again.
    } on MissingPluginException {
      // Same.
    }
  }

  @override
  Future<List<TeachLine>> teachScript() async {
    try {
      final raw = await _channel.invokeListMethod<Map<Object?, Object?>>(
        'teachScript',
      );
      return (raw ?? const [])
          .map(
            (line) => TeachLine(
              line['sentence'] as String? ?? '',
              (line['terms'] as List<Object?>? ?? const [])
                  .whereType<String>()
                  .toList(),
            ),
          )
          .toList();
    } on PlatformException {
      return const [];
    } on MissingPluginException {
      return const [];
    }
  }

  @override
  Future<List<TeachProposal>> teachProposals(
    List<(TeachLine, String)> readings,
  ) async {
    try {
      final raw = await _channel.invokeListMethod<Map<Object?, Object?>>(
        'teachProposals',
        {
          'readings': [
            for (final (line, heard) in readings)
              {'sentence': line.sentence, 'terms': line.terms, 'heard': heard},
          ],
        },
      );
      return (raw ?? const [])
          .map(
            (p) => TeachProposal(
              heard: p['heard'] as String? ?? '',
              expected: p['expected'] as String? ?? '',
              count: p['count'] as int? ?? 1,
            ),
          )
          .toList();
    } on PlatformException {
      return const [];
    } on MissingPluginException {
      return const [];
    }
  }

  static TermPack _pack(Map<Object?, Object?> raw) => TermPack(
    id: raw['id'] as String? ?? '',
    label: raw['label'] as String? ?? '',
    count: raw['count'] as int? ?? 0,
    user: raw['user'] as bool? ?? false,
  );
}
