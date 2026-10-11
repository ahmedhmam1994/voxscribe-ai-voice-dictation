import 'package:voxscribe_app/features/pro/domain/pro_repository.dart';
import 'package:voxscribe_app/features/snippets/domain/snippet.dart';
import 'package:voxscribe_app/features/snippets/domain/snippet_repository.dart';

/// Pro state kept in memory. [validKey] is the one key it accepts.
class FakeProRepository implements ProRepository {
  FakeProRepository({this.unlocked = false, this.failure});

  static const validKey = 'GOOD-KEY';

  bool unlocked;

  /// When set, every unlock attempt is refused with this message.
  String? failure;

  final activations = <String>[];
  var purchasePageOpened = false;

  @override
  Future<bool> isPro() async => unlocked;

  @override
  Future<ActivationResult> activate(String key) async {
    activations.add(key);
    if (failure case final message?) {
      return ActivationResult(ok: false, message: message);
    }
    if (key == validKey) {
      unlocked = true;
      return const ActivationResult(ok: true, message: 'activated');
    }
    return const ActivationResult(ok: false, message: 'That key is not valid.');
  }

  @override
  Future<void> deactivate() async => unlocked = false;

  @override
  Future<void> openPurchasePage() async => purchasePageOpened = true;
}

/// Snippets kept in memory. [saved] always holds what was last stored.
class FakeSnippetRepository implements SnippetRepository {
  FakeSnippetRepository([this.saved = const []]);

  List<Snippet> saved;

  @override
  Future<List<Snippet>> load() async => saved;

  @override
  Future<void> save(List<Snippet> snippets) async => saved = snippets;
}
