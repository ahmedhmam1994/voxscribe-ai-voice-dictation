import 'package:flutter/services.dart';
import 'package:voxscribe_app/features/import/domain/file_import.dart';

/// Talks to `ImportChannel.kt`.
class MethodChannelFileImportRepository implements FileImportRepository {
  static const _channel = MethodChannel('com.voxscribe.android/import');
  static const _events = EventChannel('com.voxscribe.android/import_progress');

  @override
  late final Stream<ImportProgress> progress = _events
      .receiveBroadcastStream()
      .map((raw) {
        final map = Map<String, Object?>.from(raw as Map);
        return ImportProgress(
          name: map['name'] as String? ?? '',
          atSeconds: (map['at'] as num?)?.toDouble() ?? 0,
          lengthSeconds: (map['length'] as num?)?.toDouble() ?? 0,
          index: map['index'] as int? ?? 0,
          total: map['total'] as int? ?? 1,
        );
      });

  @override
  Future<FolderStatus> folderStatus() async {
    try {
      final raw = await _channel.invokeMapMethod<String, Object?>(
        'folderStatus',
      );
      return FolderStatus(
        pro: raw?['pro'] as bool? ?? false,
        runsLeft: raw?['runsLeft'] as int? ?? 0,
      );
    } on PlatformException {
      return const FolderStatus(pro: false, runsLeft: 0);
    }
  }

  @override
  Future<FileImportResult?> transcribeFile() async {
    try {
      final raw = await _channel.invokeMapMethod<String, Object?>(
        'transcribeFile',
      );
      if (raw == null) return null;
      return FileImportResult(
        name: raw['name'] as String? ?? 'recording',
        text: raw['text'] as String? ?? '',
        srt: raw['srt'] as String? ?? '',
      );
    } on PlatformException catch (e) {
      throw ImportFailed(e.message ?? 'Could not transcribe that file.');
    }
  }

  @override
  Future<FolderImportResult?> transcribeFolder({
    required bool srt,
    required bool txt,
  }) async {
    try {
      final raw = await _channel.invokeMapMethod<String, Object?>(
        'transcribeFolder',
        {'srt': srt, 'txt': txt},
      );
      if (raw == null) return null;
      return FolderImportResult(
        done: raw['done'] as int? ?? 0,
        failed: raw['failed'] as int? ?? 0,
        total: raw['total'] as int? ?? 0,
        saved: (raw['saved'] as List?)?.cast<String>() ?? const [],
        cancelled: raw['cancelled'] as bool? ?? false,
      );
    } on PlatformException catch (e) {
      if (e.code == 'pro') throw ImportNeedsPro(e.message ?? '');
      throw ImportFailed(e.message ?? 'Could not read that folder.');
    }
  }

  @override
  Future<String?> save({
    required String name,
    required String text,
    required String mime,
  }) async {
    try {
      return await _channel.invokeMethod<String>('save', {
        'name': name,
        'text': text,
        'mime': mime,
      });
    } on PlatformException catch (e) {
      throw ImportFailed(e.message ?? 'Could not save the file.');
    }
  }

  @override
  Future<void> cancel() async {
    try {
      await _channel.invokeMethod<void>('cancel');
    } on PlatformException {
      // Nothing running.
    }
  }
}
