import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/core/dates.dart';
import 'package:voxscribe_app/features/dictation/domain/dictation_status.dart';
import 'package:voxscribe_app/features/dictation/widgets/hold_to_dictate_button.dart';
import 'package:voxscribe_app/features/notes/domain/note.dart';
import 'package:voxscribe_app/features/notes/notes_controller.dart';
import 'package:voxscribe_app/shared/widgets/vox_card.dart';

/// The notes inbox: say a thought and it is kept here with the time.
class NotesPage extends StatefulWidget {
  const NotesPage({required this.controller, super.key});

  final NotesController controller;

  @override
  State<NotesPage> createState() => _NotesPageState();
}

class _NotesPageState extends State<NotesPage> {
  @override
  void initState() {
    super.initState();
    widget.controller.load();
  }

  Future<void> _copyAll() async {
    final messenger = ScaffoldMessenger.of(context);
    final text = await widget.controller.markdown();
    await Clipboard.setData(ClipboardData(text: text));
    messenger.showSnackBar(
      const SnackBar(content: Text('All notes copied as markdown')),
    );
  }

  Future<void> _copy(Note note) async {
    final messenger = ScaffoldMessenger.of(context);
    await Clipboard.setData(ClipboardData(text: note.text));
    messenger.showSnackBar(const SnackBar(content: Text('Note copied')));
  }

  @override
  Widget build(BuildContext context) {
    final controller = widget.controller;
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        final notes = controller.notes;
        final status = _statusLine(controller);
        return Scaffold(
          appBar: AppBar(
            title: const Text('Notes inbox'),
            actions: [
              if (notes.isNotEmpty) ...[
                IconButton(
                  tooltip: 'Copy all as markdown',
                  icon: const Icon(Icons.copy_all_outlined),
                  onPressed: _copyAll,
                ),
                IconButton(
                  tooltip: 'Share all',
                  icon: const Icon(Icons.share_outlined),
                  onPressed: controller.share,
                ),
              ],
            ],
          ),
          body: Column(
            children: [
              Expanded(
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
                  children: [
                    Text(
                      'Hold the button and say a thought. It is saved here '
                      'with the time, and nothing is typed. Share your notes '
                      'as markdown to Obsidian or any notes app.',
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                    const SizedBox(height: 16),
                    if (status != null) ...[
                      Text(status, style: TextStyle(color: context.vox.muted)),
                      const SizedBox(height: 12),
                    ],
                    if (notes.isEmpty)
                      const VoxCard(
                        child: Text(
                          'No notes yet. Try "Call the dentist on Monday".',
                        ),
                      )
                    else
                      for (final (index, note) in notes.indexed) ...[
                        if (index == 0 ||
                            !isSameDay(
                              notes[index - 1].createdAt,
                              note.createdAt,
                            ))
                          _DayLabel(day: note.createdAt),
                        _NoteRow(
                          note: note,
                          onCopy: () => _copy(note),
                          onDelete: () => controller.delete(note),
                        ),
                      ],
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 10),
                child: HoldToDictateButton(
                  status: controller.status,
                  levels: controller.levels,
                  idleLabel: 'Hold to save a note',
                  recordingLabel: 'Release to save',
                  busyLabel: 'Saving...',
                  onHoldStart: controller.holdStarted,
                  onHoldEnd: controller.holdReleased,
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  String? _statusLine(NotesController controller) {
    return switch (controller.status) {
      DictationStatus.noSpeech =>
        'Nothing was saved. ${controller.nothingHeardAdvice}',
      DictationStatus.failed => controller.errorMessage,
      _ => null,
    };
  }
}

String _two(int n) => n.toString().padLeft(2, '0');

class _DayLabel extends StatelessWidget {
  const _DayLabel({required this.day});

  final DateTime day;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(2, 14, 2, 6),
      child: Text(
        '${day.year}-${_two(day.month)}-${_two(day.day)}',
        style: Theme.of(context).textTheme.labelLarge
            ?.copyWith(color: context.vox.muted),
      ),
    );
  }
}

class _NoteRow extends StatelessWidget {
  const _NoteRow({
    required this.note,
    required this.onCopy,
    required this.onDelete,
  });

  final Note note;
  final VoidCallback onCopy;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    final t = note.createdAt;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Material(
        color: c.card,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: BorderSide(color: c.border),
        ),
        child: InkWell(
          borderRadius: BorderRadius.circular(14),
          onTap: onCopy,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 10, 4, 10),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Padding(
                  padding: const EdgeInsets.only(top: 12),
                  child: Text(
                    '${_two(t.hour)}:${_two(t.minute)}',
                    style: TextStyle(
                      color: c.muted,
                      fontFeatures: const [FontFeature.tabularFigures()],
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.only(top: 12),
                    child: Text(note.text),
                  ),
                ),
                IconButton(
                  tooltip: 'Delete note',
                  icon: const Icon(Icons.delete_outline),
                  color: c.muted,
                  onPressed: onDelete,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
