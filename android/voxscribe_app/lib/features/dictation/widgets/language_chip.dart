import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/dictation/domain/dictation_language.dart';

/// Shows the language in use and opens a picker when tapped.
class LanguageChip extends StatelessWidget {
  const LanguageChip({
    required this.languageCode,
    required this.enabled,
    required this.onSelected,
    super.key,
  });

  final String languageCode;
  final bool enabled;
  final ValueChanged<String> onSelected;

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    final language = languageForCode(languageCode);
    return Semantics(
      button: true,
      enabled: enabled,
      label: 'Language: ${language.name}',
      child: ExcludeSemantics(
        child: InkWell(
          borderRadius: BorderRadius.circular(10),
          onTap: enabled ? () => _pick(context) : null,
          child: Container(
            height: 44,
            padding: const EdgeInsets.symmetric(horizontal: 12),
            decoration: BoxDecoration(
              color: c.card,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: c.border),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.language, size: 16, color: c.muted),
                const SizedBox(width: 6),
                Text(
                  language.name,
                  style: Theme.of(context).textTheme.bodySmall
                      ?.copyWith(fontWeight: FontWeight.w500),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _pick(BuildContext context) async {
    final code = await showModalBottomSheet<String>(
      context: context,
      backgroundColor: context.vox.card,
      builder: (context) => _LanguageSheet(selectedCode: languageCode),
    );
    if (code != null) onSelected(code);
  }
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
