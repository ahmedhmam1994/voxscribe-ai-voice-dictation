import 'package:voxscribe_app/features/pro/domain/pro_repository.dart';
import 'package:voxscribe_app/features/snippets/domain/snippet.dart';
import 'package:voxscribe_app/features/snippets/domain/snippet_repository.dart';
import 'package:voxscribe_app/features/texttools/domain/text_tools.dart';
import 'package:voxscribe_app/features/texttools/domain/text_tools_repository.dart';

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

  /// When true, removing the license cannot reach the server.
  bool offline = false;

  @override
  Future<ActivationResult> deactivate() async {
    unlocked = false;
    return ActivationResult(ok: !offline, message: '');
  }

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

/// Text tool settings kept in memory. [saved] always holds what was last stored.
class FakeTextToolsRepository implements TextToolsRepository {
  FakeTextToolsRepository([this.saved = TextToolsSettings.defaults]);

  TextToolsSettings saved;

  @override
  Future<TextToolsSettings> load() async => saved;

  @override
  Future<void> save(TextToolsSettings settings) async => saved = settings;
}
