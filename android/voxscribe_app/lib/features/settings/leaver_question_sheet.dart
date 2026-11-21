import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/settings/domain/settings_repository.dart';

/// The fixed answers, by the key the usage ping sends (`LeaverQuestion.kt`).
const leaverReasons = <(String, String)>[
  ('wrong_words', 'It got my words wrong'),
  ('too_slow', 'It was too slow'),
  ('no_text', "The text didn't appear in my app"),
  ('button_in_way', 'The floating button got in the way'),
  ('button_gone', 'The floating button kept disappearing'),
  ('forgot', 'I forgot it was there'),
  ('rarely_need', "I don't need dictation often"),
  ('busy', "Nothing, I've just been busy"),
  ('other', 'Something else'),
];

/// Asked once, after a few days without a dictation. Any way out of the
/// sheet counts as asked, so it never comes back.
Future<void> showLeaverQuestionSheet(
  BuildContext context,
  SettingsRepository repository,
) async {
  final messenger = ScaffoldMessenger.of(context);
  final reason = await showModalBottomSheet<String>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (sheetContext) {
      final vox = sheetContext.vox;
      return SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 4, 24, 12),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Quick question',
                style: TextStyle(
                  color: vox.text,
                  fontSize: 22,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                "You haven't dictated in a few days. If something put you "
                'off, tap what fits so the right thing gets fixed. This is '
                'asked once and sends only your choice, with no name.',
                style: TextStyle(color: vox.muted),
              ),
              const SizedBox(height: 8),
              Flexible(
                child: ListView(
                  shrinkWrap: true,
                  children: [
                    for (final (key, label) in leaverReasons)
                      ListTile(
                        contentPadding: EdgeInsets.zero,
                        title: Text(label),
                        onTap: () => Navigator.of(sheetContext).pop(key),
                      ),
                  ],
                ),
              ),
              Align(
                alignment: Alignment.centerRight,
                child: TextButton(
                  onPressed: () => Navigator.of(sheetContext).pop(),
                  child: const Text("Don't ask"),
                ),
              ),
            ],
          ),
        ),
      );
    },
  );
  await repository.answerLeaverQuestion(reason);
  if (reason != null) {
    messenger.showSnackBar(
      const SnackBar(content: Text('Thanks, that helps.')),
    );
  }
}
