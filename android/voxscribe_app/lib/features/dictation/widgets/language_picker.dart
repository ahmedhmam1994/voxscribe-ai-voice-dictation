import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/dictation/domain/dictation_language.dart';

/// Opens the language list and returns the chosen code, or null if dismissed.
Future<String?> pickLanguage(BuildContext context, String selectedCode) {
  return showModalBottomSheet<String>(
    context: context,
    backgroundColor: context.vox.card,
    isScrollControlled: true,
    constraints: BoxConstraints(
      maxHeight: MediaQuery.sizeOf(context).height * 0.85,
    ),
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
                subtitle: language.native == language.name
                    ? null
                    : Text(language.native, style: TextStyle(color: c.muted)),
                trailing: language.code == selectedCode
                    ? Icon(Icons.check, color: c.accentInk)
                    : null,
                onTap: () => Navigator.of(context).pop(language.code),
              ),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
              child: Text(
                'English, French, German, Italian, Portuguese and Spanish '
                'share one speech model (536 MB); the other languages share '
                'another (682 MB). Picking a language whose model is not on '
                'the phone offers to download it.',
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
