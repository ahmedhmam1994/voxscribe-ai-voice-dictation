import 'package:flutter/material.dart';
import 'package:voxscribe_app/features/setup/setup_controller.dart';
import 'package:voxscribe_app/features/setup/setup_screen.dart';

/// The setup screen as its own page, opened from Settings, with a back button.
class SetupPage extends StatelessWidget {
  const SetupPage({required this.controller, super.key});

  final SetupController controller;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Align(
              alignment: Alignment.centerLeft,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(8, 8, 0, 0),
                child: IconButton(
                  tooltip: 'Back',
                  icon: const Icon(Icons.arrow_back),
                  onPressed: () => Navigator.of(context).maybePop(),
                ),
              ),
            ),
            Expanded(child: SetupScreen(controller: controller)),
          ],
        ),
      ),
    );
  }
}
