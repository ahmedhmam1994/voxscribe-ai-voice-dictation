import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/features/pro/pro_controller.dart';

import 'support/fake_pro_repository.dart';

void main() {
  test('starts locked', () async {
    final controller = ProController(repository: FakeProRepository());

    await controller.load();

    expect(controller.isPro, isFalse);
  });

  test('picks up a license that is already saved', () async {
    final controller = ProController(
      repository: FakeProRepository(unlocked: true),
    );

    await controller.load();

    expect(controller.isPro, isTrue);
  });

  test('a good key unlocks Pro', () async {
    final controller = ProController(repository: FakeProRepository());

    await controller.activate(FakeProRepository.validKey);

    expect(controller.isPro, isTrue);
    expect(controller.errorMessage, isNull);
    expect(controller.busy, isFalse);
  });

  test('a bad key stays locked and says why', () async {
    final controller = ProController(repository: FakeProRepository());

    await controller.activate('WRONG');

    expect(controller.isPro, isFalse);
    expect(controller.errorMessage, 'That key is not valid.');
  });

  test('the server message is shown when the key is refused', () async {
    final controller = ProController(
      repository: FakeProRepository(
        failure: 'This key is already activated on a different device.',
      ),
    );

    await controller.activate(FakeProRepository.validKey);

    expect(controller.errorMessage, contains('already activated'));
  });

  test('an empty key is not sent anywhere', () async {
    final repository = FakeProRepository();
    final controller = ProController(repository: repository);

    await controller.activate('   ');

    expect(repository.activations, isEmpty);
    expect(controller.errorMessage, isNotNull);
  });

  test('removing the license locks Pro again', () async {
    final controller = ProController(
      repository: FakeProRepository(unlocked: true),
    );
    await controller.load();

    await controller.deactivate();

    expect(controller.isPro, isFalse);
  });
}
