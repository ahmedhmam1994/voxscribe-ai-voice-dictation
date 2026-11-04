import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/features/texttools/domain/text_tools.dart';
import 'package:voxscribe_app/features/texttools/text_tools_controller.dart';

import 'support/fake_pro_repository.dart';
import 'support/test_app.dart';

void main() {
  test('form filling is on by default and the switch saves', () async {
    expect(TextToolsSettings.defaults.formFill, isTrue);
    final repo = FakeTextToolsRepository();
    final tools = TextToolsController(repository: repo);
    await tools.setFormFill(value: false);
    expect(repo.saved.formFill, isFalse);
  });

  testWidgets('Settings explains form filling and counts the free fills', (
    tester,
  ) async {
    useTallScreen(tester);
    final repo = FakeTextToolsRepository(
      const TextToolsSettings(formFillsLeft: 3),
    );
    await tester.pumpWidget(buildTestApp(textTools: repo));
    await tester.pumpAndSettle();
    await openTab(tester, 'Settings');

    expect(find.text('Fill forms by voice'), findsOneWidget);
    expect(find.textContaining('3 free fills left'), findsOneWidget);
  });
}
