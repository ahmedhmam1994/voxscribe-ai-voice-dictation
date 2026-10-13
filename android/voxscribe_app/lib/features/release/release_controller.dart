import 'package:flutter/foundation.dart';
import 'package:voxscribe_app/features/release/domain/release.dart';
import 'package:voxscribe_app/features/release/domain/release_repository.dart';
import 'package:voxscribe_app/features/release/whats_new.dart';

/// Decides when to tell the user about a release: the "what's new" notes the
/// first time a new version opens, and a banner when a newer one is published.
class ReleaseController extends ChangeNotifier {
  ReleaseController({required this.repository});

  final ReleaseRepository repository;

  String _version = '';
  List<String>? _notes;
  ReleaseInfo? _update;

  /// The installed version, e.g. "1.0.0".
  String get version => _version;

  /// Notes to show now, or null when there is nothing new to announce.
  List<String>? get pendingNotes => _notes;

  /// A newer published release to offer, or null.
  ReleaseInfo? get update => _update;

  Future<void> start() async {
    final saved = await repository.state();
    _version = saved.version;
    final notes = whatsNewFor(saved.version);
    if (saved.lastSeen != saved.version) {
      if (notes != null) {
        _notes = notes;
      } else {
        // A version with nothing to announce still counts as seen.
        await repository.markSeen(saved.version);
      }
    }
    notifyListeners();

    final latest = await repository.fetchLatest();
    if (latest != null &&
        isNewerVersion(latest.version, saved.version) &&
        latest.version != saved.dismissedUpdate) {
      _update = latest;
      notifyListeners();
    }
  }

  Future<void> dismissNotes() async {
    _notes = null;
    notifyListeners();
    await repository.markSeen(_version);
  }

  Future<void> dismissUpdate() async {
    final current = _update;
    if (current == null) return;
    _update = null;
    notifyListeners();
    await repository.dismissUpdate(current.version);
  }

  Future<void> openUpdate() async {
    final current = _update;
    if (current != null) await repository.open(current.downloadUrl);
  }
}
