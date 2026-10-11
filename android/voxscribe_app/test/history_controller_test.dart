import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/features/history/domain/dictation_entry.dart';
import 'package:voxscribe_app/features/history/history_controller.dart';

import 'support/fake_history_repository.dart';

DictationEntry _entry(String text) => DictationEntry(
  text: text,
  createdAt: DateTime(2026, 10, 10, 9),
  duration: const Duration(seconds: 2),
);

void main() {
  test('starts empty and loads what is saved', () async {
    final controller = HistoryController(
      repository: FakeHistoryRepository([_entry('already saved')]),
    );
    expect(controller.entries, isEmpty);

    await controller.load();

    expect(controller.entries.map((e) => e.text), ['already saved']);
  });

  test('adding saves the entry and shows it first', () async {
    final controller = HistoryController(
      repository: FakeHistoryRepository([_entry('older')]),
    );
    await controller.load();

    await controller.add(_entry('newer'));

    expect(controller.entries.map((e) => e.text), ['newer', 'older']);
  });

  test('clearing removes everything', () async {
    final controller = HistoryController(
      repository: FakeHistoryRepository([_entry('one'), _entry('two')]),
    );
    await controller.load();

    await controller.clear();

    expect(controller.entries, isEmpty);
  });

  test('listeners hear about changes', () async {
    final controller = HistoryController(repository: FakeHistoryRepository());
    var notifications = 0;
    controller.addListener(() => notifications++);

    await controller.add(_entry('hello'));

    expect(notifications, greaterThan(0));
  });
}
