import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/shell/vox_nav_bar.dart';
import 'package:voxscribe_app/features/dictation/dictation_controller.dart';
import 'package:voxscribe_app/features/dictation/dictation_screen.dart';
import 'package:voxscribe_app/features/dictation/domain/dictation_engine.dart';
import 'package:voxscribe_app/features/history/domain/history_repository.dart';
import 'package:voxscribe_app/features/history/history_controller.dart';
import 'package:voxscribe_app/features/insights/insights_screen.dart';
import 'package:voxscribe_app/features/pro/domain/pro_repository.dart';
import 'package:voxscribe_app/features/pro/pro_controller.dart';
import 'package:voxscribe_app/features/settings/settings_controller.dart';
import 'package:voxscribe_app/features/settings/settings_screen.dart';
import 'package:voxscribe_app/features/setup/domain/setup_platform.dart';
import 'package:voxscribe_app/features/setup/setup_controller.dart';
import 'package:voxscribe_app/features/snippets/domain/snippet_repository.dart';
import 'package:voxscribe_app/features/snippets/snippets_controller.dart';

/// The three top-level sections with a bottom navigation bar.
class HomeShell extends StatefulWidget {
  const HomeShell({
    required this.engine,
    required this.setupPlatform,
    required this.historyRepository,
    required this.proRepository,
    required this.snippetRepository,
    required this.settings,
    super.key,
  });

  final DictationEngine engine;
  final SetupPlatform setupPlatform;
  final HistoryRepository historyRepository;
  final ProRepository proRepository;
  final SnippetRepository snippetRepository;
  final SettingsController settings;

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  static const _destinations = [
    NavDestination(label: 'Dictation', icon: Icons.mic_none),
    NavDestination(label: 'Insights', icon: Icons.bar_chart),
    NavDestination(label: 'Settings', icon: Icons.tune),
  ];

  late final HistoryController _history = HistoryController(
    repository: widget.historyRepository,
  );
  late final DictationController _dictation = DictationController(
    engine: widget.engine,
    history: _history,
  );
  late final SetupController _setup = SetupController(
    platform: widget.setupPlatform,
  );
  late final ProController _pro = ProController(
    repository: widget.proRepository,
  );
  late final SnippetsController _snippets = SnippetsController(
    repository: widget.snippetRepository,
  );
  late final AppLifecycleListener _lifecycle;
  var _index = 0;

  @override
  void initState() {
    super.initState();
    // The floating button saves dictations and permissions can change while
    // the app is away, so look again whenever it comes back.
    _lifecycle = AppLifecycleListener(onResume: _refresh);
    _refresh();
    _dictation.loadLanguage();
  }

  void _refresh() {
    _history.load();
    _setup.refresh();
    _pro.load();
  }

  @override
  void dispose() {
    _lifecycle.dispose();
    _dictation.dispose();
    _history.dispose();
    _setup.dispose();
    _pro.dispose();
    _snippets.dispose();
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
            DictationScreen(controller: _dictation, history: _history),
            InsightsScreen(history: _history),
            SettingsScreen(
              settings: widget.settings,
              setup: _setup,
              dictation: _dictation,
              history: _history,
              pro: _pro,
              snippets: _snippets,
            ),
          ],
        ),
      ),
      bottomNavigationBar: VoxNavBar(
        destinations: _destinations,
        selectedIndex: _index,
        onSelected: (index) {
          setState(() => _index = index);
          _refresh();
        },
      ),
    );
  }
}
