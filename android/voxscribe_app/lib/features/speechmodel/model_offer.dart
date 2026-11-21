import 'package:flutter/material.dart';
import 'package:voxscribe_app/features/dictation/domain/dictation_language.dart';
import 'package:voxscribe_app/features/setup/setup_controller.dart';

/// After a language change: when the speech model for the new language is
/// not on the phone, asks to download it, because dictation cannot type that
/// language without it.
Future<void> offerSpeechModel(
  BuildContext context,
  SetupController setup,
) async {
  final status = setup.status;
  if (!setup.loaded || status.modelInstalled || status.modelDownloading) {
    return;
  }
  final language = languageForCode(status.language).name;
  final download = await showModalBottomSheet<bool>(
    context: context,
    showDragHandle: true,
    builder: (context) => SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(24, 0, 24, 16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Download the $language model',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text(
              'VoxScribe types $language with a speech model that runs on '
              'this phone. It downloads once (${status.modelMegabytes} MB, so '
              'use Wi-Fi), then works offline. Until then dictation cannot '
              'type $language.',
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton(
                  onPressed: () => Navigator.pop(context, false),
                  child: const Text('Later'),
                ),
                const SizedBox(width: 8),
                FilledButton(
                  onPressed: () => Navigator.pop(context, true),
                  child: const Text('Download'),
                ),
              ],
            ),
          ],
        ),
      ),
    ),
  );
  if (download == true) await setup.downloadModel();
}
