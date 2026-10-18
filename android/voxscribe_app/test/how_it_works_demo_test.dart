import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/setup/widgets/how_it_works_demo.dart';

Widget _host() => MaterialApp(
  theme: ThemeData(extensions: const [VoxColors.dark]),
  home: const Scaffold(body: HowItWorksDemo()),
);

void main() {
  testWidgets('loops and keeps painting', (tester) async {
    await tester.pumpWidget(_host());
    await tester.pump(const Duration(seconds: 2));
    await tester.pump(const Duration(seconds: 6));
    expect(find.byType(HowItWorksDemo), findsOneWidget);
    expect(tester.binding.hasScheduledFrame, isTrue);
  });

  testWidgets('stands still with reduced motion', (tester) async {
    tester.platformDispatcher.accessibilityFeaturesTestValue =
        const FakeAccessibilityFeatures(disableAnimations: true);
    addTearDown(tester.platformDispatcher.clearAccessibilityFeaturesTestValue);
    await tester.pumpWidget(_host());
    await tester.pumpAndSettle();
    expect(tester.binding.hasScheduledFrame, isFalse);
  });

  testWidgets('describes itself for screen readers', (tester) async {
    await tester.pumpWidget(_host());
    expect(
      find.bySemanticsLabel(RegExp('hold the floating button')),
      findsOneWidget,
    );
  });
}
