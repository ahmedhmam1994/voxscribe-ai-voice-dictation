import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/features/release/domain/release.dart';
import 'package:voxscribe_app/features/release/release_controller.dart';

import 'support/fake_release_repository.dart';
import 'support/test_app.dart';

const _apkJson = '''
[
  {"tag_name": "v1.7.2", "draft": false, "prerelease": false,
   "html_url": "https://github.com/o/r/releases/tag/v1.7.2", "assets": []},
  {"tag_name": "android-v1.0.1", "draft": false, "prerelease": false,
   "body": " Fixes ", "html_url": "https://github.com/o/r/releases/tag/android-v1.0.1",
   "assets": [
     {"name": "notes.txt", "browser_download_url": "https://github.com/x/notes.txt"},
     {"name": "VoxScribe.apk", "browser_download_url": "https://github.com/x/VoxScribe.apk"}
   ]},
  {"tag_name": "android-v1.0.2", "draft": true, "prerelease": false, "assets": []},
  {"tag_name": "android-v1.1.0", "draft": false, "prerelease": true, "assets": []}
]
''';

void main() {
  group('versions', () {
    test('compare numerically, not as text', () {
      expect(isNewerVersion('1.10.0', '1.9.0'), isTrue);
      expect(isNewerVersion('1.0.0', '1.0.0'), isFalse);
      expect(isNewerVersion('1.0', '1.0.1'), isFalse);
      expect(isNewerVersion('android-v2.0.0', '1.9.9'), isTrue);
    });
  });

  group('parseLatestAndroidRelease', () {
    test('ignores Windows tags, drafts and prereleases, finds the apk', () {
      final latest = parseLatestAndroidRelease(_apkJson)!;
      expect(latest.version, '1.0.1');
      expect(latest.notes, 'Fixes');
      expect(latest.downloadUrl, 'https://github.com/x/VoxScribe.apk');
    });

    test('falls back to the release page without an apk', () {
      final latest = parseLatestAndroidRelease(
        '[{"tag_name":"android-v1.0.1","html_url":"https://github.com/o/r/p","assets":[]}]',
      )!;
      expect(latest.downloadUrl, 'https://github.com/o/r/p');
    });

    test('returns null for nothing usable', () {
      expect(parseLatestAndroidRelease('not json'), isNull);
      expect(parseLatestAndroidRelease('{}'), isNull);
      expect(parseLatestAndroidRelease('[]'), isNull);
    });
  });

  group('ReleaseController', () {
    test('shows notes the first time a version with notes opens', () async {
      final repo = FakeReleaseRepository(lastSeen: null);
      final controller = ReleaseController(repository: repo);
      await controller.start();
      expect(controller.pendingNotes, isNotNull);
      await controller.dismissNotes();
      expect(controller.pendingNotes, isNull);
      expect(repo.lastSeen, '1.0.0');
    });

    test('stays quiet when the notes were already seen', () async {
      final controller = ReleaseController(repository: FakeReleaseRepository());
      await controller.start();
      expect(controller.pendingNotes, isNull);
    });

    test('a version without notes is marked seen silently', () async {
      final repo = FakeReleaseRepository(version: '1.0.9', lastSeen: '1.0.0');
      final controller = ReleaseController(repository: repo);
      await controller.start();
      expect(controller.pendingNotes, isNull);
      expect(repo.lastSeen, '1.0.9');
    });

    test('offers a newer release and remembers a dismissal', () async {
      final repo = FakeReleaseRepository(
        latest: parseLatestAndroidRelease(_apkJson),
      );
      final controller = ReleaseController(repository: repo);
      await controller.start();
      expect(controller.update?.version, '1.0.1');
      await controller.openUpdate();
      expect(repo.opened, ['https://github.com/x/VoxScribe.apk']);
      await controller.dismissUpdate();
      expect(controller.update, isNull);

      final again = ReleaseController(repository: repo);
      await again.start();
      expect(again.update, isNull);
    });

    test('offers nothing when already on the newest version', () async {
      final repo = FakeReleaseRepository(
        version: '1.0.1',
        latest: parseLatestAndroidRelease(_apkJson),
      );
      final controller = ReleaseController(repository: repo);
      await controller.start();
      expect(controller.update, isNull);
    });
  });

  group('screens', () {
    testWidgets('first launch of a new version shows the notes sheet', (
      tester,
    ) async {
      await tester.pumpWidget(
        buildTestApp(release: FakeReleaseRepository(lastSeen: null)),
      );
      await tester.pumpAndSettle();
      expect(find.text("What's new in 1.0.0"), findsOneWidget);
      await tester.tap(find.text('Got it'));
      await tester.pumpAndSettle();
      expect(find.text("What's new in 1.0.0"), findsNothing);
    });

    testWidgets('a newer release shows the update banner', (tester) async {
      final repo = FakeReleaseRepository(
        latest: parseLatestAndroidRelease(_apkJson),
      );
      await tester.pumpWidget(buildTestApp(release: repo));
      await tester.pumpAndSettle();
      expect(find.text('VoxScribe 1.0.1 is available'), findsOneWidget);
      await tester.tap(find.text('Update'));
      await tester.pump();
      expect(repo.opened, hasLength(1));
      await tester.tap(find.byTooltip('Dismiss'));
      await tester.pumpAndSettle();
      expect(find.text('VoxScribe 1.0.1 is available'), findsNothing);
    });
  });
}
