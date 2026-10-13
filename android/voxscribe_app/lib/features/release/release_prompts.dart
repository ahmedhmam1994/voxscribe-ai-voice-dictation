import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/release/release_controller.dart';

/// The "new version available" strip at the top of the app.
class UpdateBanner extends StatelessWidget {
  const UpdateBanner({required this.controller, super.key});

  final ReleaseController controller;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        final update = controller.update;
        if (update == null) return const SizedBox.shrink();
        final vox = context.vox;
        return Container(
          margin: const EdgeInsets.fromLTRB(16, 8, 16, 0),
          padding: const EdgeInsets.fromLTRB(16, 4, 4, 4),
          decoration: BoxDecoration(
            color: vox.card,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: vox.accent.withValues(alpha: 0.5)),
          ),
          child: Row(
            children: [
              Icon(Icons.system_update_alt, color: vox.accentInk, size: 20),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  'VoxScribe ${update.version} is available',
                  style: TextStyle(
                    color: vox.text,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              TextButton(
                onPressed: controller.openUpdate,
                child: Text('Update', style: TextStyle(color: vox.accentInk)),
              ),
              IconButton(
                tooltip: 'Dismiss',
                onPressed: controller.dismissUpdate,
                icon: Icon(Icons.close, color: vox.muted, size: 18),
              ),
            ],
          ),
        );
      },
    );
  }
}

/// The notes sheet shown the first time a new version opens.
Future<void> showWhatsNewSheet(
  BuildContext context,
  ReleaseController controller,
) async {
  final notes = controller.pendingNotes;
  if (notes == null) return;
  final version = controller.version;
  await showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (sheetContext) {
      final vox = sheetContext.vox;
      return SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 4, 24, 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                "What's new in $version",
                style: TextStyle(
                  color: vox.text,
                  fontSize: 22,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 16),
              for (final note in notes)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Padding(
                        padding: const EdgeInsets.only(top: 2),
                        child: Icon(
                          Icons.check,
                          color: vox.accentInk,
                          size: 18,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          note,
                          style: TextStyle(color: vox.text, height: 1.35),
                        ),
                      ),
                    ],
                  ),
                ),
              const SizedBox(height: 8),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: () => Navigator.of(sheetContext).pop(),
                  child: const Text('Got it'),
                ),
              ),
            ],
          ),
        ),
      );
    },
  );
  await controller.dismissNotes();
}
