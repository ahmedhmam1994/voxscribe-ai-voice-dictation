import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/import/data/method_channel_file_import_repository.dart';
import 'package:voxscribe_app/features/import/domain/file_import.dart';
import 'package:voxscribe_app/features/import/file_import_controller.dart';
import 'package:voxscribe_app/shared/widgets/section_label.dart';
import 'package:voxscribe_app/shared/widgets/vox_card.dart';

/// Transcribe an audio or video file, or a whole folder, on the phone.
class FileImportScreen extends StatefulWidget {
  const FileImportScreen({this.repository, super.key});

  /// Replaced in tests.
  final FileImportRepository? repository;

  @override
  State<FileImportScreen> createState() => _FileImportScreenState();
}

class _FileImportScreenState extends State<FileImportScreen> {
  late final FileImportController _controller = FileImportController(
    repository: widget.repository ?? MethodChannelFileImportRepository(),
  )..load();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context).textTheme;
    final c = context.vox;
    return Scaffold(
      appBar: AppBar(title: const Text('Transcribe a file')),
      body: ListenableBuilder(
        listenable: _controller,
        builder: (context, _) {
          final ctl = _controller;
          final status = ctl.status;
          return ListView(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
            children: [
              Text(
                'Turn a voice note, recording or video into text and captions. '
                'It all happens on this phone; nothing is uploaded.',
                style: theme.bodyMedium?.copyWith(color: c.muted),
              ),
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: ctl.busy ? null : ctl.transcribeFile,
                icon: const Icon(Icons.audio_file_outlined),
                label: const Text('Choose a file'),
                style: FilledButton.styleFrom(
                  minimumSize: const Size.fromHeight(52),
                ),
              ),
              const SizedBox(height: 10),
              OutlinedButton.icon(
                onPressed: ctl.busy || !status.allowed
                    ? null
                    : ctl.transcribeFolder,
                icon: const Icon(Icons.folder_open_outlined),
                label: Text(
                  status.pro
                      ? 'Choose a folder'
                      : status.runsLeft > 0
                      ? 'Choose a folder (${status.runsLeft} free '
                            '${status.runsLeft == 1 ? 'try' : 'tries'} left)'
                      : 'Choose a folder (Pro)',
                ),
                style: OutlinedButton.styleFrom(
                  minimumSize: const Size.fromHeight(52),
                ),
              ),
              const SizedBox(height: 6),
              Row(
                children: [
                  Expanded(
                    child: CheckboxListTile(
                      value: ctl.saveSrt,
                      onChanged: ctl.busy
                          ? null
                          : (v) => ctl.setSaveSrt(value: v ?? false),
                      title: const Text('Captions (.srt)'),
                      contentPadding: EdgeInsets.zero,
                      controlAffinity: ListTileControlAffinity.leading,
                    ),
                  ),
                  Expanded(
                    child: CheckboxListTile(
                      value: ctl.saveTxt,
                      onChanged: ctl.busy
                          ? null
                          : (v) => ctl.setSaveTxt(value: v ?? false),
                      title: const Text('Text (.txt)'),
                      contentPadding: EdgeInsets.zero,
                      controlAffinity: ListTileControlAffinity.leading,
                    ),
                  ),
                ],
              ),
              Text(
                'A folder saves these next to every audio and video file in it, '
                'and never replaces a file that is already there.',
                style: theme.bodySmall,
              ),
              if (ctl.busy) ...[
                const SizedBox(height: 20),
                _Progress(progress: ctl.progress, onCancel: ctl.cancel),
              ],
              if (ctl.message case final message?) ...[
                const SizedBox(height: 16),
                Text(message, style: theme.bodyMedium),
              ],
              if (ctl.file case final file? when file.text.isNotEmpty) ...[
                SectionLabel(file.name),
                VoxCard(
                  child: SelectableText(file.text, style: theme.bodyLarge),
                ),
                const SizedBox(height: 10),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    OutlinedButton.icon(
                      onPressed: () =>
                          Clipboard.setData(ClipboardData(text: file.text)),
                      icon: const Icon(Icons.copy_outlined, size: 18),
                      label: const Text('Copy'),
                    ),
                    OutlinedButton.icon(
                      onPressed: () => ctl.saveFile(captions: false),
                      icon: const Icon(Icons.description_outlined, size: 18),
                      label: const Text('Save .txt'),
                    ),
                    OutlinedButton.icon(
                      onPressed: () => ctl.saveFile(captions: true),
                      icon: const Icon(Icons.subtitles_outlined, size: 18),
                      label: const Text('Save captions .srt'),
                    ),
                  ],
                ),
              ],
            ],
          );
        },
      ),
    );
  }
}

/// 754.2 -> "12:34", 3725 -> "1:02:05".
String _clock(double seconds) {
  final s = seconds.floor();
  final h = s ~/ 3600;
  final m = (s ~/ 60) % 60;
  final sec = (s % 60).toString().padLeft(2, '0');
  return h > 0 ? '$h:${m.toString().padLeft(2, '0')}:$sec' : '$m:$sec';
}

class _Progress extends StatelessWidget {
  const _Progress({required this.progress, required this.onCancel});

  final ImportProgress? progress;
  final VoidCallback onCancel;

  @override
  Widget build(BuildContext context) {
    final p = progress;
    final theme = Theme.of(context).textTheme;
    final c = context.vox;
    final label = p == null
        ? 'Starting...'
        : p.total > 1
        ? 'File ${p.index + 1} of ${p.total}: ${p.name}'
        : p.name;
    return VoxCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: theme.bodyMedium,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 10),
          LinearProgressIndicator(
            value: p?.fraction,
            minHeight: 6,
            borderRadius: BorderRadius.circular(4),
            color: c.accent,
            // A clearly different track, so a half-done bar never looks full.
            backgroundColor: c.raised,
          ),
          const SizedBox(height: 8),
          if (p != null && p.atSeconds > 0)
            Text(
              p.lengthSeconds > 0
                  ? '${_clock(p.atSeconds)} of ${_clock(p.lengthSeconds)} '
                        '(${(p.fraction! * 100).round()}%)'
                  : '${_clock(p.atSeconds)} done',
              style: theme.bodyMedium?.copyWith(
                fontFeatures: const [FontFeature.tabularFigures()],
              ),
            ),
          Row(
            children: [
              Expanded(
                child: Text(
                  'Long recordings take a while. You can keep using the phone.',
                  style: theme.bodySmall,
                ),
              ),
              TextButton(onPressed: onCancel, child: const Text('Cancel')),
            ],
          ),
        ],
      ),
    );
  }
}
