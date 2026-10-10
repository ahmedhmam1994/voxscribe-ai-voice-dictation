import 'package:voxscribe_app/features/history/domain/dictation_entry.dart';
import 'package:voxscribe_app/features/history/domain/history_repository.dart';

/// History kept in memory, newest first, like the real store.
class FakeHistoryRepository implements HistoryRepository {
  FakeHistoryRepository([List<DictationEntry> entries = const []])
    : _entries = [...entries];

  final List<DictationEntry> _entries;

  @override
  Future<List<DictationEntry>> load() async => List.of(_entries);

  @override
  Future<void> add(DictationEntry entry) async => _entries.insert(0, entry);

  @override
  Future<void> clear() async => _entries.clear();
}
