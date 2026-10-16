import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/texttools/domain/corrections.dart';
import 'package:voxscribe_app/features/texttools/text_tools_controller.dart';

/// Lets the user fix a word that was heard wrong: pick it from [text], say what
/// it should be, and from then on VoxScribe types that instead. It becomes a
/// word replacement, so nothing is sent anywhere and nothing about other apps
/// is read: only the history VoxScribe already keeps on the phone.
Future<void> showFixWordSheet(
  BuildContext context, {
  required String text,
  required TextToolsController textTools,
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (sheetContext) => Padding(
      padding: EdgeInsets.only(
        bottom: MediaQuery.viewInsetsOf(sheetContext).bottom,
      ),
      child: _FixWordSheet(text: text, textTools: textTools),
    ),
  );
}

class _FixWordSheet extends StatefulWidget {
  const _FixWordSheet({required this.text, required this.textTools});

  final String text;
  final TextToolsController textTools;

  @override
  State<_FixWordSheet> createState() => _FixWordSheetState();
}

class _FixWordSheetState extends State<_FixWordSheet> {
  final _replacement = TextEditingController();
  String? _picked;
  String? _error;

  @override
  void dispose() {
    _replacement.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final picked = _picked;
    if (picked == null) return;
    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);
    final replacement = _replacement.text.trim();
    final status = await widget.textTools.addCorrection(picked, replacement);
    switch (status) {
      case CorrectionStatus.invalid:
        setState(() => _error = 'Type what it should be instead.');
      case CorrectionStatus.unchanged:
        navigator.pop();
        messenger.showSnackBar(
          const SnackBar(content: Text('That correction is already saved.')),
        );
      case CorrectionStatus.added || CorrectionStatus.updated:
        navigator.pop();
        messenger.showSnackBar(
          SnackBar(
            content: Text(
              'Done. VoxScribe will type "$replacement" instead of "$picked".',
            ),
          ),
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    final theme = Theme.of(context).textTheme;
    final picked = _picked;
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 4, 20, 20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Fix a word', style: theme.titleLarge),
            const SizedBox(height: 6),
            Text(
              picked == null
                  ? 'Tap the word that was heard wrong.'
                  : 'From now on VoxScribe will type your version instead of '
                        '"$picked".',
              style: theme.bodyMedium?.copyWith(color: c.muted),
            ),
            const SizedBox(height: 14),
            Flexible(
              child: SingleChildScrollView(
                child: Wrap(
                  spacing: 8,
                  runSpacing: 4,
                  children: [
                    for (final word in wordsOf(widget.text))
                      ChoiceChip(
                        label: Text(word),
                        selected:
                            picked != null &&
                            cleanHeard(word).toLowerCase() ==
                                picked.toLowerCase(),
                        onSelected: (_) => setState(() {
                          _picked = cleanHeard(word);
                          _error = null;
                          _replacement.clear();
                        }),
                      ),
                  ],
                ),
              ),
            ),
            if (picked != null) ...[
              const SizedBox(height: 14),
              TextField(
                controller: _replacement,
                autofocus: true,
                textInputAction: TextInputAction.done,
                onSubmitted: (_) => _save(),
                decoration: InputDecoration(
                  labelText: 'Type this instead',
                  errorText: _error,
                ),
              ),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: _save,
                  child: const Text('Save correction'),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
