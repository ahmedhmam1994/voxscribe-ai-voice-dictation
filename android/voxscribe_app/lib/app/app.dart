import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/shell/home_shell.dart';
import 'package:voxscribe_app/app/theme/app_theme.dart';
import 'package:voxscribe_app/features/dictation/domain/dictation_engine.dart';
import 'package:voxscribe_app/features/setup/domain/setup_platform.dart';

class VoxScribeApp extends StatelessWidget {
  const VoxScribeApp({
    required this.engine,
    required this.setupPlatform,
    super.key,
  });

  final DictationEngine engine;
  final SetupPlatform setupPlatform;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'VoxScribe',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      darkTheme: AppTheme.dark,
      themeMode: ThemeMode.system,
      home: HomeShell(engine: engine, setupPlatform: setupPlatform),
    );
  }
}
