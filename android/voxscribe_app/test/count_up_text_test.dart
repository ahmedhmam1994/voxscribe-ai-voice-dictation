import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/shared/widgets/count_up_text.dart';

Widget _host(int value, {bool still = false}) => MaterialApp(
  home: MediaQuery(
    data: MediaQueryData(disableAnimations: still),
    child: Scaffold(
      body: CountUpText(value: value, format: (n) => '$n words'),
    ),
  ),
);

void main() {
  testWidgets('counts up and ends on the real number', (tester) async {
    await tester.pumpWidget(_host(120));
    expect(find.text('120 words'), findsNothing);
    await tester.pumpAndSettle();
    expect(find.text('120 words'), findsOneWidget);
  });

  testWidgets('counts from the old number to a new one', (tester) async {
    await tester.pumpWidget(_host(100));
    await tester.pumpAndSettle();
    await tester.pumpWidget(_host(200));
    await tester.pump(const Duration(milliseconds: 50));
    final shown = tester.widget<Text>(find.byType(Text)).data!;
    final n = int.parse(shown.split(' ').first);
    expect(n, inInclusiveRange(100, 199));
    await tester.pumpAndSettle();
    expect(find.text('200 words'), findsOneWidget);
  });

  testWidgets('with reduced motion the number shows at once', (tester) async {
    await tester.pumpWidget(_host(42, still: true));
    await tester.pump();
    expect(find.text('42 words'), findsOneWidget);
  });
}
