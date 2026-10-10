import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/dictation/domain/dictation_language.dart';
import 'package:voxscribe_app/features/dictation/widgets/language_picker.dart';

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
    final code = await pickLanguage(context, languageCode);
    if (code != null) onSelected(code);
  }
}
