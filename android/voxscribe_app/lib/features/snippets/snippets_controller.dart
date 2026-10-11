import 'package:flutter/foundation.dart';
import 'package:voxscribe_app/features/snippets/domain/snippet.dart';
import 'package:voxscribe_app/features/snippets/domain/snippet_repository.dart';

/// The user's snippets. A change shows immediately and is then saved.
class SnippetsController extends ChangeNotifier {
  SnippetsController({required this.repository});

  final SnippetRepository repository;

  List<Snippet> _snippets = const [];

  List<Snippet> get snippets => _snippets;

  Future<void> load() async {
    _snippets = await repository.load();
    notifyListeners();
  }

  /// Adds [snippet], or replaces the one that already has the same trigger.
  Future<void> save(Snippet snippet) => replace(null, snippet);

  /// Swaps [old] for [next]; a null [old] just adds. Another snippet with
  /// [next]'s trigger is replaced too, so a trigger is never listed twice.
  Future<void> replace(Snippet? old, Snippet next) {
    final others = _snippets.where((s) => s != old && !s.hasSameTrigger(next));
    return _store([...others, next]);
  }

  Future<void> remove(Snippet snippet) =>
      _store(_snippets.where((s) => s != snippet).toList());

  Future<void> _store(List<Snippet> next) {
    _snippets = next;
    notifyListeners();
    return repository.save(next);
  }
}
