import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/features/snippets/domain/snippet.dart';
import 'package:voxscribe_app/features/snippets/snippets_controller.dart';

import 'support/fake_pro_repository.dart';

const _email = Snippet(trigger: 'my email', expansion: 'me@example.com');

void main() {
  test('loads what was saved', () async {
    final controller = SnippetsController(
      repository: FakeSnippetRepository([_email]),
    );

    await controller.load();

    expect(controller.snippets, [_email]);
  });

  test('a new snippet shows at once and is saved', () async {
    final repository = FakeSnippetRepository();
    final controller = SnippetsController(repository: repository);

    final saving = controller.save(_email);
    expect(controller.snippets, [_email]);
    await saving;

    expect(repository.saved, [_email]);
  });

  test('the same trigger in another case replaces the old snippet', () async {
    final controller = SnippetsController(
      repository: FakeSnippetRepository([_email]),
    );
    await controller.load();

    await controller.save(
      const Snippet(trigger: 'My Email', expansion: 'new@example.com'),
    );

    expect(controller.snippets, hasLength(1));
    expect(controller.snippets.single.expansion, 'new@example.com');
  });

  test('editing a trigger does not leave the old one behind', () async {
    final controller = SnippetsController(
      repository: FakeSnippetRepository([_email]),
    );
    await controller.load();

    await controller.replace(
      _email,
      const Snippet(trigger: 'work email', expansion: 'me@example.com'),
    );

    expect(controller.snippets.map((s) => s.trigger), ['work email']);
  });

  test('removing a snippet saves the shorter list', () async {
    final repository = FakeSnippetRepository([_email]);
    final controller = SnippetsController(repository: repository);
    await controller.load();

    await controller.remove(controller.snippets.single);

    expect(repository.saved, isEmpty);
  });
}
