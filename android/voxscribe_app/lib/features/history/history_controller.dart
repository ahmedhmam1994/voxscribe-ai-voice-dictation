import 'package:flutter/foundation.dart';
import 'package:voxscribe_app/features/history/domain/dictation_entry.dart';
import 'package:voxscribe_app/features/history/domain/history_repository.dart';

/// Holds the saved dictations for the screens that show them.
class HistoryController extends ChangeNotifier {
  HistoryController({required this.repository});

  final HistoryRepository repository;

  List<DictationEntry> _entries = const [];

  /// Every saved dictation, newest first.
  List<DictationEntry> get entries => _entries;

  /// Reads the store again. Call when the app returns to the foreground,
  /// since the floating button saves dictations while it is away.
  Future<void> load() async {
    _entries = await repository.load();
    notifyListeners();
  }

  Future<void> add(DictationEntry entry) async {
    await repository.add(entry);
    await load();
  }

  Future<void> clear() async {
    await repository.clear();
    await load();
  }
}
