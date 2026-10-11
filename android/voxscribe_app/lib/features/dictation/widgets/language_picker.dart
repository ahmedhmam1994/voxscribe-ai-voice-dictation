import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/dictation/domain/dictation_language.dart';

/// Opens the language list and returns the chosen code, or null if dismissed.
Future<String?> pickLanguage(BuildContext context, String selectedCode) {
  return showModalBottomSheet<String>(
    context: context,
    backgroundColor: context.vox.card,
    builder: (context) => _LanguageSheet(selectedCode: selectedCode),
  );
}

class _LanguageSheet extends StatelessWidget {
  const _LanguageSheet({required this.selectedCode});

  final String selectedCode;

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    return SafeArea(
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 20, 20, 8),
              child: Text(
                'Language you speak',
                style: Theme.of(context).textTheme.labelSmall,
              ),
            ),
            for (final language in dictationLanguages)
              ListTile(
                minTileHeight: 52,
                title: Text(language.name),
                trailing: language.code == selectedCode
                    ? Icon(Icons.check, color: c.accentInk)
                    : null,
                onTap: () => Navigator.of(context).pop(language.code),
              ),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
              child: Text(
                'Auto-detect can guess wrong on a phone microphone. Pick the '
                'language you are speaking for the best results.',
                style: Theme.of(context).textTheme.bodySmall
                    ?.copyWith(color: c.muted),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
