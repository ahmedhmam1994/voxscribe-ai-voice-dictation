import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/features/texttools/domain/text_tools.dart';
import 'package:voxscribe_app/features/texttools/text_tools_controller.dart';

import 'support/fake_pro_repository.dart';
import 'support/test_app.dart';

void main() {
  test('screen spelling is on by default and the switch saves', () async {
    expect(TextToolsSettings.defaults.screenSpelling, isTrue);
    final repo = FakeTextToolsRepository();
    final tools = TextToolsController(repository: repo);
    await tools.setScreenSpelling(value: false);
    expect(repo.saved.screenSpelling, isFalse);
    expect(repo.saved.formFill, isTrue);
  });

  testWidgets('Settings has the switch and says the screen is never kept', (
    tester,
  ) async {
    useTallScreen(tester);
    final repo = FakeTextToolsRepository();
    await tester.pumpWidget(buildTestApp(textTools: repo));
    await tester.pumpAndSettle();
    await openTab(tester, 'Settings');

    expect(find.text('Spell names from the screen'), findsOneWidget);
    expect(find.textContaining('never kept'), findsOneWidget);
    await tester.tap(find.text('Spell names from the screen'));
    await tester.pumpAndSettle();
    expect(repo.saved.screenSpelling, isFalse);
  });
}
