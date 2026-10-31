import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/dictation/dictation_controller.dart';
import 'package:voxscribe_app/features/dictation/domain/dictation_status.dart';
import 'package:voxscribe_app/features/dictation/widgets/typing_text.dart';
import 'package:voxscribe_app/features/dictation/widgets/voice_waveform.dart';

/// The latest dictation, or a hint before the first one. While recording it
/// shows the live waveform of your voice instead; on release the waveform
/// squeezes down into a line and the words type in where it was.
class TranscriptCard extends StatelessWidget {
  const TranscriptCard({
    required this.transcript,
    this.status = DictationStatus.ready,
    this.waveform = const [],
    super.key,
  });

  static const double _minHeight = 108;

  final String? transcript;
  final DictationStatus status;

  /// The current recording's input levels, oldest first.
  final List<double> waveform;

  bool get _listening =>
      status == DictationStatus.recording ||
      status == DictationStatus.transcribing;

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    final text = transcript;
    final Widget body;
    if (_listening) {
      body = SizedBox(
        key: const ValueKey('wave'),
        height: _minHeight,
        child: _LiveWave(
          levels: waveform,
          collapsing: status == DictationStatus.transcribing,
        ),
      );
    } else if (text == null) {
      body = Text(
        'Hold the green button and talk. Your words appear here.',
        key: const ValueKey('hint'),
        style: Theme.of(context).textTheme.bodyLarge?.copyWith(color: c.muted),
      );
    } else {
      body = TypingText(text, key: const ValueKey('text'));
    }
    return AnimatedContainer(
      duration: const Duration(milliseconds: 250),
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: c.card,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: status == DictationStatus.recording
              ? c.accent.withValues(alpha: 0.55)
              : c.border,
        ),
      ),
      child: ConstrainedBox(
        constraints: const BoxConstraints(minHeight: _minHeight),
        child: AnimatedSwitcher(
          duration: const Duration(milliseconds: 220),
          layoutBuilder: (current, previous) => Stack(
            alignment: Alignment.topLeft,
            children: [...previous, ?current],
          ),
          child: body,
        ),
      ),
    );
  }
}

/// The waveform while recording. When [collapsing] turns true (transcribing),
/// it squeezes to a thin line in the middle and fades, handing over to the text.
class _LiveWave extends StatefulWidget {
  const _LiveWave({required this.levels, required this.collapsing});

  final List<double> levels;
  final bool collapsing;

  @override
  State<_LiveWave> createState() => _LiveWaveState();
}

class _LiveWaveState extends State<_LiveWave>
    with SingleTickerProviderStateMixin {
  late final AnimationController _collapse = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 420),
  );

  @override
  void didUpdateWidget(_LiveWave oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.collapsing && !oldWidget.collapsing) {
      if (MediaQuery.disableAnimationsOf(context)) {
        _collapse.value = 1;
      } else {
        _collapse.forward(from: 0);
      }
    } else if (!widget.collapsing && oldWidget.collapsing) {
      _collapse.value = 0;
    }
  }

  @override
  void dispose() {
    _collapse.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final wave = VoiceWaveform(
      levels: widget.levels,
      color: context.vox.accent,
      slots: DictationController.waveformBars,
    );
    return AnimatedBuilder(
      animation: _collapse,
      builder: (context, child) {
        final t = Curves.easeInCubic.transform(_collapse.value);
        return Opacity(
          opacity: 1 - t,
          child: Transform.scale(
            scaleX: 1 - 0.9 * t,
            scaleY: 1 - 0.97 * t,
            child: child,
          ),
        );
      },
      child: wave,
    );
  }
}
