import 'package:voxscribe_app/features/release/domain/release.dart';

abstract interface class ReleaseRepository {
  Future<ReleaseState> state();

  /// Remember that this version's "what's new" has been shown.
  Future<void> markSeen(String version);

  /// Hide the update banner until a still newer version appears.
  Future<void> dismissUpdate(String version);

  /// The newest Android release on GitHub, or null when offline or none.
  Future<ReleaseInfo?> fetchLatest();

  Future<void> open(String url);
}
