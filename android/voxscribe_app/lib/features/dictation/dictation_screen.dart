import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/core/dates.dart';
import 'package:voxscribe_app/features/dictation/dictation_controller.dart';
import 'package:voxscribe_app/features/dictation/widgets/fix_word_sheet.dart';
import 'package:voxscribe_app/features/dictation/widgets/hold_to_dictate_button.dart';
import 'package:voxscribe_app/features/dictation/widgets/language_chip.dart';
import 'package:voxscribe_app/features/dictation/widgets/status_pill.dart';
import 'package:voxscribe_app/features/dictation/widgets/today_list.dart';
import 'package:voxscribe_app/features/dictation/widgets/transcript_actions.dart';
import 'package:voxscribe_app/features/dictation/widgets/transcript_card.dart';
import 'package:voxscribe_app/features/history/history_controller.dart';
import 'package:voxscribe_app/features/dictation/domain/dictation_engine.dart';
import 'package:voxscribe_app/features/import/file_import_screen.dart';
import 'package:voxscribe_app/features/notes/data/method_channel_notes_repository.dart';
import 'package:voxscribe_app/features/notes/notes_controller.dart';
import 'package:voxscribe_app/features/notes/notes_page.dart';
import 'package:voxscribe_app/features/readaloud/read_aloud.dart';
import 'package:voxscribe_app/features/setup/setup_controller.dart';
import 'package:voxscribe_app/features/setup/setup_screen.dart';
import 'package:voxscribe_app/features/setup/widgets/practice_card.dart';
import 'package:voxscribe_app/features/setup/widgets/setup_reminder_card.dart';
import 'package:voxscribe_app/features/texttools/text_tools_controller.dart';
import 'package:voxscribe_app/shared/widgets/brand_mark.dart';
import 'package:voxscribe_app/shared/widgets/section_label.dart';

/// Dictate from inside the app and see the latest transcript and history.
class DictationScreen extends StatelessWidget {
  const DictationScreen({
    required this.controller,
    required this.history,
    required this.textTools,
    required this.setup,
    this.readAloud = const MethodChannelReadAloud(),
    this.engine,
    super.key,
  });

  /// The recorder the notes inbox uses. Null hides the notes button.
  final DictationEngine? engine;

  final DictationController controller;
  final HistoryController history;
  final TextToolsController textTools;
  final SetupController setup;

  /// Reads a transcript aloud with the phone's voice.
  final ReadAloud readAloud;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: Listenable.merge([controller, history, setup]),
      builder: (context, _) {
        // A new install starts on the setup steps, not on an empty screen.
        if (setup.firstRun) {
          return SetupScreen(controller: setup, onSkip: setup.finishFirstRun);
        }
        final hasTranscript = controller.transcript != null;
        final now = DateTime.now();
        final today = history.entries
            .where((entry) => isSameDay(entry.createdAt, now))
            .toList();
        return Column(
          children: [
            _AppBar(controller: controller, engine: engine),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
                children: [
                  if (setup.showReminder) SetupReminderCard(controller: setup),
                  if (setup.showPractice)
                    PracticeCard(onDone: setup.hidePractice),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: StatusPill(
                      status: controller.status,
                      levels: controller.recentLevels,
                      errorMessage: controller.errorMessage,
                      readyLabel: !setup.loaded || setup.status.modelInstalled
                          ? 'Ready'
                          : setup.status.modelDownloading
                          ? 'Waiting for the speech model'
                          : 'Speech model needed',
                    ),
                  ),
                  if (controller.nothingHeardAdvice case final advice?)
                    Padding(
                      padding: const EdgeInsets.only(top: 8),
                      child: Text(
                        advice,
                        style: Theme.of(context).textTheme.bodyMedium
                            ?.copyWith(color: context.vox.muted),
                      ),
                    ),
                  const SectionLabel('Transcript'),
                  TranscriptCard(
                    transcript: controller.transcript,
                    status: controller.status,
                    waveform: controller.waveform,
                  ),
                  const SizedBox(height: 10),
                  TranscriptActions(
                    onCopy: hasTranscript ? () => _copy(controller) : null,
                    onFixWord: hasTranscript
                        ? () => showFixWordSheet(
                            context,
                            text: controller.transcript!,
                            textTools: textTools,
                          )
                        : null,
                    onClear: hasTranscript ? controller.clearTranscript : null,
                    onListen: () =>
                        readAloud.speak(controller.transcript ?? ''),
                  ),
                  const SectionLabel('Today'),
                  TodayList(
                    entries: today,
                    onFixWord: (text) => showFixWordSheet(
                      context,
                      text: text,
                      textTools: textTools,
                    ),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 10),
              child: HoldToDictateButton(
                status: controller.status,
                levels: controller.recentLevels,
                invite: history.entries.isEmpty,
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
  const _AppBar({required this.controller, this.engine});

  final DictationController controller;
  final DictationEngine? engine;

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
          if (engine case final engine?)
            IconButton(
              tooltip: 'Notes inbox',
              icon: const Icon(Icons.sticky_note_2_outlined),
              onPressed: controller.canStart
                  ? () => _openNotes(context, engine)
                  : null,
            ),
          IconButton(
            tooltip: 'Transcribe an audio or video file',
            icon: const Icon(Icons.audio_file_outlined),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(builder: (_) => const FileImportScreen()),
            ),
          ),
          const SizedBox(width: 4),
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

Future<void> _openNotes(BuildContext context, DictationEngine engine) async {
  final notes = NotesController(
    engine: engine,
    repository: const MethodChannelNotesRepository(),
  );
  await Navigator.of(
    context,
  ).push(MaterialPageRoute<void>(builder: (_) => NotesPage(controller: notes)));
  notes.dispose();
}
