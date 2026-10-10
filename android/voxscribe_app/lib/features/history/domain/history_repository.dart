import 'package:voxscribe_app/features/history/domain/dictation_entry.dart';

/// Where finished dictations are kept. Both the floating button and the
/// in-app button write to the same store.
abstract interface class HistoryRepository {
  /// Every saved dictation, newest first.
  Future<List<DictationEntry>> load();

  Future<void> add(DictationEntry entry);

  Future<void> clear();
}
