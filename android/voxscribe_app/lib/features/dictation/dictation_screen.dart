import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:voxscribe_app/core/dates.dart';
import 'package:voxscribe_app/features/dictation/dictation_controller.dart';
import 'package:voxscribe_app/features/dictation/widgets/hold_to_dictate_button.dart';
import 'package:voxscribe_app/features/dictation/widgets/language_chip.dart';
import 'package:voxscribe_app/features/dictation/widgets/status_pill.dart';
import 'package:voxscribe_app/features/dictation/widgets/today_list.dart';
import 'package:voxscribe_app/features/dictation/widgets/transcript_actions.dart';
import 'package:voxscribe_app/features/dictation/widgets/transcript_card.dart';
import 'package:voxscribe_app/features/history/history_controller.dart';
import 'package:voxscribe_app/shared/widgets/brand_mark.dart';
import 'package:voxscribe_app/shared/widgets/section_label.dart';

/// Dictate from inside the app and see the latest transcript and history.
class DictationScreen extends StatelessWidget {
  const DictationScreen({
    required this.controller,
    required this.history,
    super.key,
  });

  final DictationController controller;
  final HistoryController history;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: Listenable.merge([controller, history]),
      builder: (context, _) {
        final hasTranscript = controller.transcript != null;
        final now = DateTime.now();
        final today = history.entries
            .where((entry) => isSameDay(entry.createdAt, now))
            .toList();
        return Column(
          children: [
            _AppBar(controller: controller),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
                children: [
                  Align(
                    alignment: Alignment.centerLeft,
                    child: StatusPill(
                      status: controller.status,
                      levels: controller.recentLevels,
                      errorMessage: controller.errorMessage,
                    ),
                  ),
                  const SectionLabel('Transcript'),
                  TranscriptCard(transcript: controller.transcript),
                  const SizedBox(height: 10),
                  TranscriptActions(
                    onCopy: hasTranscript ? () => _copy(controller) : null,
                    onClear: hasTranscript ? controller.clearTranscript : null,
                  ),
                  const SectionLabel('Today'),
                  TodayList(entries: today),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 10),
              child: HoldToDictateButton(
                status: controller.status,
                onHoldStart: controller.holdStarted,
                onHoldEnd: controller.holdReleased,
              ),
            ),
          ],
        );
      },
    );
  }

  Future<void> _copy(DictationController controller) {
    return Clipboard.setData(ClipboardData(text: controller.transcript!));
  }
}

class _AppBar extends StatelessWidget {
  const _AppBar({required this.controller});

  final DictationController controller;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 6),
      child: Row(
        children: [
          const BrandMark(),
          const SizedBox(width: 10),
          Text(
            'VoxScribe',
            style: Theme.of(context).textTheme.titleLarge
                ?.copyWith(fontSize: 19, letterSpacing: -0.2),
          ),
          const Spacer(),
          LanguageChip(
            languageCode: controller.language,
            enabled: controller.canStart,
            onSelected: controller.chooseLanguage,
          ),
        ],
      ),
    );
  }
}
