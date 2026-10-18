import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/import/domain/file_import.dart';
import 'package:voxscribe_app/features/import/file_import_controller.dart';
import 'package:voxscribe_app/features/import/file_import_screen.dart';

class FakeImport implements FileImportRepository {
  FakeImport({this.status = const FolderStatus(pro: false, runsLeft: 2)});

  FolderStatus status;
  FileImportResult? file = const FileImportResult(
    name: 'talk.mp4',
    text: 'Hello from the file.',
    srt: '1\n00:00:00,000 --> 00:00:02,000\nHello from the file.\n\n',
  );
  Object? folderError;
  final saves = <({String name, String mime})>[];
  ({bool srt, bool txt})? folderAsked;
  final _progress = StreamController<ImportProgress>.broadcast();

  @override
  Stream<ImportProgress> get progress => _progress.stream;

  @override
  Future<FolderStatus> folderStatus() async => status;

  @override
  Future<FileImportResult?> transcribeFile() async => file;

  @override
  Future<FolderImportResult?> transcribeFolder({
    required bool srt,
    required bool txt,
  }) async {
    folderAsked = (srt: srt, txt: txt);
    if (folderError case final error?) throw error;
    status = FolderStatus(pro: status.pro, runsLeft: status.runsLeft - 1);
    return const FolderImportResult(
      done: 3,
      failed: 1,
      total: 4,
      saved: ['a.srt', 'b.srt', 'c.srt'],
      cancelled: false,
    );
  }

  @override
  Future<String?> save({
    required String name,
    required String text,
    required String mime,
  }) async {
    saves.add((name: name, mime: mime));
    return name;
  }

  @override
  Future<void> cancel() async {}
}

void main() {
  test(
    'one file shows its text and saves captions under its own name',
    () async {
      final repo = FakeImport();
      final ctl = FileImportController(repository: repo);
      await ctl.transcribeFile();
      expect(ctl.file?.text, 'Hello from the file.');
      await ctl.saveFile(captions: true);
      expect(repo.saves.single.name, 'talk.srt');
      expect(repo.saves.single.mime, 'application/x-subrip');
      await ctl.saveFile(captions: false);
      expect(repo.saves.last.name, 'talk.txt');
    },
  );

  test('a folder run reports what it saved and uses a free try', () async {
    final repo = FakeImport();
    final ctl = FileImportController(repository: repo);
    await ctl.load();
    await ctl.transcribeFolder();
    expect(ctl.message, contains('Transcribed 3 of 4'));
    expect(ctl.message, contains('1 could not be read'));
    expect(ctl.status.runsLeft, 1);
    expect(repo.folderAsked, (srt: true, txt: false));
  });

  test('at least one kind of file stays selected for folders', () {
    final ctl = FileImportController(repository: FakeImport());
    ctl.setSaveSrt(value: false);
    expect(ctl.saveSrt, isTrue);
    ctl
      ..setSaveTxt(value: true)
      ..setSaveSrt(value: false);
    expect(ctl.saveSrt, isFalse);
    expect(ctl.saveTxt, isTrue);
  });

  test('a folder without Pro or free tries says so', () async {
    final repo = FakeImport(status: const FolderStatus(pro: false, runsLeft: 0))
      ..folderError = const ImportNeedsPro(
        'Transcribing a whole folder needs Pro.',
      );
    final ctl = FileImportController(repository: repo);
    await ctl.transcribeFolder();
    expect(ctl.message, contains('needs Pro'));
  });

  testWidgets('the screen shows free tries and the transcript', (tester) async {
    final repo = FakeImport();
    await tester.pumpWidget(
      MaterialApp(
        theme: ThemeData(extensions: const [VoxColors.dark]),
        home: FileImportScreen(repository: repo),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Choose a folder (2 free tries left)'), findsOneWidget);
    await tester.tap(find.text('Choose a file'));
    await tester.pumpAndSettle();
    expect(find.text('Hello from the file.'), findsOneWidget);
    expect(find.text('Save captions .srt'), findsOneWidget);
  });
}

