import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/dictation/widgets/typing_text.dart';
import 'package:voxscribe_app/shared/widgets/vox_card.dart';

/// The latest dictation, or a hint before the first one.
class TranscriptCard extends StatelessWidget {
  const TranscriptCard({required this.transcript, super.key});

  final String? transcript;

  @override
  Widget build(BuildContext context) {
    final text = transcript;
    return VoxCard(
      child: ConstrainedBox(
        constraints: const BoxConstraints(minHeight: 108),
        child: text == null
            ? Text(
                'Hold the green button and talk. Your words appear here.',
                style: Theme.of(context).textTheme.bodyLarge
                    ?.copyWith(color: context.vox.muted),
              )
            : TypingText(text),
      ),
    );
  }
}
