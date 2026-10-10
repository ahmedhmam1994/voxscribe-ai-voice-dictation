import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/shell/home_shell.dart';
import 'package:voxscribe_app/app/theme/app_theme.dart';
import 'package:voxscribe_app/features/dictation/domain/dictation_engine.dart';
import 'package:voxscribe_app/features/history/domain/history_repository.dart';
import 'package:voxscribe_app/features/settings/domain/app_settings.dart';
import 'package:voxscribe_app/features/settings/domain/settings_repository.dart';
import 'package:voxscribe_app/features/settings/settings_controller.dart';
import 'package:voxscribe_app/features/setup/domain/setup_platform.dart';

class VoxScribeApp extends StatefulWidget {
  const VoxScribeApp({
    required this.engine,
    required this.setupPlatform,
    required this.historyRepository,
    required this.settingsRepository,
    super.key,
  });

  final DictationEngine engine;
  final SetupPlatform setupPlatform;
  final HistoryRepository historyRepository;
  final SettingsRepository settingsRepository;

  @override
  State<VoxScribeApp> createState() => _VoxScribeAppState();
}

class _VoxScribeAppState extends State<VoxScribeApp> {
  // Lives here, above MaterialApp, because the theme choice changes it.
  late final SettingsController _settings = SettingsController(
    repository: widget.settingsRepository,
  );

  @override
  void initState() {
    super.initState();
    _settings.load();
  }

  @override
  void dispose() {
    _settings.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: _settings,
      builder: (context, _) {
        return MaterialApp(
          title: 'VoxScribe',
          debugShowCheckedModeBanner: false,
          theme: AppTheme.light,
          darkTheme: AppTheme.dark,
          themeMode: switch (_settings.settings.theme) {
            ThemeChoice.system => ThemeMode.system,
            ThemeChoice.light => ThemeMode.light,
            ThemeChoice.dark => ThemeMode.dark,
          },
          home: HomeShell(
            engine: widget.engine,
            setupPlatform: widget.setupPlatform,
            historyRepository: widget.historyRepository,
            settings: _settings,
          ),
        );
      },
    );
  }
}
