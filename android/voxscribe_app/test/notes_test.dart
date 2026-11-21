import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/app/theme/app_theme.dart';
import 'package:voxscribe_app/features/dictation/domain/dictation_status.dart';
import 'package:voxscribe_app/features/notes/domain/note.dart';
import 'package:voxscribe_app/features/notes/domain/notes_repository.dart';
import 'package:voxscribe_app/features/notes/notes_controller.dart';
import 'package:voxscribe_app/features/notes/notes_page.dart';

import 'support/scripted_engine.dart';

class _FakeNotes implements NotesRepository {
  final saved = <Note>[];
  var shared = 0;

  @override
  Future<List<Note>> load() async => List.of(saved);

  @override
  Future<Note?> add(String text) async {
    if (text.trim().isEmpty) return null;
    final note = Note(
      id: saved.length + 1,
      text: text,
      createdAt: DateTime(2026, 11, 19, 9, 5),
    );
    saved.insert(0, note);
    return note;
  }

  @override
  Future<void> delete(int id) async => saved.removeWhere((n) => n.id == id);

  @override
  Future<String> markdown() async => '# VoxScribe Inbox\n';

  @override
  Future<void> share() async => shared++;
}

Widget testApp(Widget page) => MaterialApp(theme: AppTheme.light, home: page);

void main() {
  test('a spoken thought is saved as a note, nothing typed', () async {
    final engine = ScriptedEngine();
    final repo = _FakeNotes();
    final notes = NotesController(engine: engine, repository: repo);
    await notes.holdStarted();
    expect(notes.status, DictationStatus.recording);
    final released = notes.holdReleased();
    engine.finish('Call the dentist on Monday');
    await released;
    expect(notes.status, DictationStatus.ready);
    expect(notes.notes.single.text, 'Call the dentist on Monday');
    expect(repo.saved, hasLength(1));
  });

  test('silence saves nothing', () async {
    final engine = ScriptedEngine();
    final repo = _FakeNotes();
    final notes = NotesController(engine: engine, repository: repo);
    await notes.holdStarted();
    final released = notes.holdReleased();
    engine.finish('   ');
    await released;
    expect(notes.status, DictationStatus.noSpeech);
    expect(repo.saved, isEmpty);
  });

  test('deleting a note removes it', () async {
    final repo = _FakeNotes();
    await repo.add('one');
    await repo.add('two');
    final notes = NotesController(engine: ScriptedEngine(), repository: repo);
    await notes.load();
    await notes.delete(notes.notes.first);
    expect(notes.notes.map((n) => n.text), ['one']);
    expect(repo.saved.map((n) => n.text), ['one']);
  });

  testWidgets('the page lists notes with their time and can share them', (
    tester,
  ) async {
    final repo = _FakeNotes();
    await repo.add('Buy milk');
    final notes = NotesController(engine: ScriptedEngine(), repository: repo);
    await tester.pumpWidget(testApp(NotesPage(controller: notes)));
    await tester.pumpAndSettle();
    expect(find.text('Buy milk'), findsOneWidget);
    expect(find.text('09:05'), findsOneWidget);
    expect(find.text('Hold to save a note'), findsOneWidget);
    await tester.tap(find.byTooltip('Share all'));
    expect(repo.shared, 1);
  });

  testWidgets('an empty inbox says how to start', (tester) async {
    final notes = NotesController(
      engine: ScriptedEngine(),
      repository: _FakeNotes(),
    );
    await tester.pumpWidget(testApp(NotesPage(controller: notes)));
    await tester.pumpAndSettle();
    expect(find.textContaining('No notes yet'), findsOneWidget);
    expect(find.byType(IconButton), findsNothing);
  });
}
