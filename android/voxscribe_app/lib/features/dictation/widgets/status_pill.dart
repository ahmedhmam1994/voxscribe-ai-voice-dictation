import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/dictation/dictation_controller.dart';
import 'package:voxscribe_app/features/dictation/domain/dictation_status.dart';
import 'package:voxscribe_app/features/dictation/widgets/level_meter.dart';

/// Shows what the dictation flow is doing, with a live meter while recording.
class StatusPill extends StatelessWidget {
  const StatusPill({
    required this.status,
    required this.levels,
    this.errorMessage,
    super.key,
  });

  final DictationStatus status;
  final List<double> levels;
  final String? errorMessage;

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    final tone = _tone(c);
    final neutral = tone == c.muted;
    return Semantics(
      liveRegion: true,
      container: true,
      child: Container(
        height: 40,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        decoration: BoxDecoration(
          color: c.card,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(
            color: neutral ? c.softBorder : tone.withValues(alpha: 0.5),
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(color: tone, shape: BoxShape.circle),
            ),
            const SizedBox(width: 10),
            if (status == DictationStatus.recording) ...[
              LevelMeter(
                levels: levels,
                color: tone,
                barCount: DictationController.meterBars,
              ),
              const SizedBox(width: 10),
            ],
            Flexible(
              child: Text(
                _label,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodyMedium
                    ?.copyWith(fontWeight: FontWeight.w500),
              ),
            ),
          ],
        ),
      ),
    );
  }

  String get _label => switch (status) {
    DictationStatus.ready => 'Ready',
    DictationStatus.recording => 'Listening',
    DictationStatus.transcribing => 'Transcribing',
    DictationStatus.noSpeech => 'No speech heard',
    DictationStatus.failed => errorMessage ?? 'Something went wrong',
  };

  Color _tone(VoxColors c) => switch (status) {
    DictationStatus.recording => c.accentInk,
    DictationStatus.transcribing => c.amber,
    DictationStatus.failed => c.red,
    DictationStatus.ready || DictationStatus.noSpeech => c.muted,
  };
}
