import 'package:flutter/widgets.dart';
import 'package:voxscribe_app/app/app.dart';
import 'package:voxscribe_app/features/dictation/data/method_channel_dictation_engine.dart';
import 'package:voxscribe_app/features/history/data/method_channel_history_repository.dart';
import 'package:voxscribe_app/features/settings/data/method_channel_settings_repository.dart';
import 'package:voxscribe_app/features/setup/data/method_channel_setup_platform.dart';

void main() {
  runApp(
    VoxScribeApp(
      engine: MethodChannelDictationEngine(),
      setupPlatform: MethodChannelSetupPlatform(),
      historyRepository: MethodChannelHistoryRepository(),
      settingsRepository: MethodChannelSettingsRepository(),
    ),
  );
}
