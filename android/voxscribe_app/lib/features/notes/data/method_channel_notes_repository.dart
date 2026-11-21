import 'package:flutter/services.dart';
import 'package:voxscribe_app/features/notes/domain/note.dart';
import 'package:voxscribe_app/features/notes/domain/notes_repository.dart';

/// Talks to `NotesChannel.kt`.
class MethodChannelNotesRepository implements NotesRepository {
  const MethodChannelNotesRepository();

  static const _channel = MethodChannel('com.voxscribe.android/notes');

  @override
  Future<List<Note>> load() async {
    try {
      final raw = await _channel.invokeListMethod<Map<Object?, Object?>>(
        'getNotes',
      );
      return [for (final item in raw ?? const []) _fromMap(item)];
    } on PlatformException {
      return const [];
    }
  }

  @override
  Future<Note?> add(String text) async {
    try {
      final raw = await _channel.invokeMapMethod<Object?, Object?>('addNote', {
        'text': text,
      });
      return raw == null ? null : _fromMap(raw);
    } on PlatformException {
      return null;
    }
  }

  @override
  Future<void> delete(int id) async {
    try {
      await _channel.invokeMethod<void>('deleteNote', {'id': id});
    } on PlatformException {
      // The next load shows what is still there.
    }
  }

  @override
  Future<String> markdown() async {
    try {
      return await _channel.invokeMethod<String>('markdown') ?? '';
    } on PlatformException {
      return '';
    }
  }

  @override
  Future<void> share() async {
    try {
      await _channel.invokeMethod<void>('share');
    } on PlatformException {
      // Nothing to share with; the notes stay where they are.
    }
  }

  Note _fromMap(Map<Object?, Object?> map) {
    return Note(
      id: (map['id'] as num?)?.toInt() ?? 0,
      text: map['text'] as String? ?? '',
      createdAt: DateTime.fromMillisecondsSinceEpoch(
        (map['at'] as num?)?.toInt() ?? 0,
      ),
    );
  }
}
