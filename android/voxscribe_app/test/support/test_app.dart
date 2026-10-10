import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/app/app.dart';
import 'package:voxscribe_app/app/shell/vox_nav_bar.dart';

import 'fake_history_repository.dart';
import 'fake_settings_repository.dart';
import 'fake_setup_platform.dart';
import 'scripted_engine.dart';

/// The whole app wired to fakes. Pass any of them to control or inspect it.
Widget buildTestApp({
  ScriptedEngine? engine,
  FakeSetupPlatform? setup,
  FakeHistoryRepository? history,
  FakeSettingsRepository? settings,
}) {
  return VoxScribeApp(
    engine: engine ?? ScriptedEngine(),
    setupPlatform: setup ?? FakeSetupPlatform(),
    historyRepository: history ?? FakeHistoryRepository(),
    settingsRepository: settings ?? FakeSettingsRepository(),
  );
}

/// Taps a bottom navigation tab by its label.
Future<void> openTab(WidgetTester tester, String label) async {
  await tester.tap(
    find.descendant(of: find.byType(VoxNavBar), matching: find.text(label)),
  );
  await tester.pumpAndSettle();
}

/// Gives the test a tall, phone-sized screen so a whole list is on screen.
void useTallScreen(WidgetTester tester) {
  tester.view.physicalSize = const Size(900, 2400);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
}
