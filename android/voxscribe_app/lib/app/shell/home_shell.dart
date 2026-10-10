import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/shell/vox_nav_bar.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/dictation/dictation_controller.dart';
import 'package:voxscribe_app/features/dictation/dictation_screen.dart';
import 'package:voxscribe_app/features/dictation/domain/dictation_engine.dart';
import 'package:voxscribe_app/features/setup/domain/setup_platform.dart';
import 'package:voxscribe_app/features/setup/setup_controller.dart';
import 'package:voxscribe_app/features/setup/setup_screen.dart';

/// The three top-level sections with a bottom navigation bar.
class HomeShell extends StatefulWidget {
  const HomeShell({
    required this.engine,
    required this.setupPlatform,
    super.key,
  });

  final DictationEngine engine;
  final SetupPlatform setupPlatform;

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  static const _destinations = [
    NavDestination(label: 'Dictation', icon: Icons.mic_none),
    NavDestination(label: 'Insights', icon: Icons.bar_chart),
    NavDestination(label: 'Setup', icon: Icons.checklist),
  ];

  late final DictationController _dictation = DictationController(
    engine: widget.engine,
  );
  late final SetupController _setup = SetupController(
    platform: widget.setupPlatform,
  );
  var _index = 0;

  @override
  void initState() {
    super.initState();
    _dictation.loadLanguage();
  }

  @override
  void dispose() {
    _dictation.dispose();
    _setup.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: IndexedStack(
          index: _index,
          children: [
            DictationScreen(controller: _dictation),
            const _NotBuiltYet('Insights'),
            SetupScreen(controller: _setup),
          ],
        ),
      ),
      bottomNavigationBar: VoxNavBar(
        destinations: _destinations,
        selectedIndex: _index,
        onSelected: (index) => setState(() => _index = index),
      ),
    );
  }
}

/// Stands in for a section whose screen has not been built yet.
class _NotBuiltYet extends StatelessWidget {
  const _NotBuiltYet(this.title);

  final String title;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Text(
        '$title comes next.',
        style: Theme.of(context).textTheme.bodyLarge
            ?.copyWith(color: context.vox.muted),
      ),
    );
  }
}
