import 'package:voxscribe_app/features/release/domain/release.dart';
import 'package:voxscribe_app/features/release/domain/release_repository.dart';

class FakeReleaseRepository implements ReleaseRepository {
  FakeReleaseRepository({
    this.version = '1.0.0',
    this.lastSeen = '1.0.0',
    this.dismissed,
    this.latest,
  });

  final String version;
  String? lastSeen;
  String? dismissed;
  ReleaseInfo? latest;
  final opened = <String>[];

  @override
  Future<ReleaseState> state() async => ReleaseState(
    version: version,
    lastSeen: lastSeen,
    dismissedUpdate: dismissed,
  );

  @override
  Future<void> markSeen(String version) async => lastSeen = version;

  @override
  Future<void> dismissUpdate(String version) async => dismissed = version;

  @override
  Future<ReleaseInfo?> fetchLatest() async => latest;

  @override
  Future<void> open(String url) async => opened.add(url);
}
