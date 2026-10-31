import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/dictation/domain/dictation_status.dart';
import 'package:voxscribe_app/features/dictation/widgets/level_meter.dart';

/// The big green button. Hold to record, release to transcribe.
///
/// While recording it grows a little and shows the live mic level in place of
/// the mic icon; while transcribing a small spinner turns. When [invite] is
/// on (before the first dictation) a soft ring breathes out from it three
/// times, so a new user knows where to press. The ring is decoration and stays still with
/// reduced motion; the level is information and always moves.
class HoldToDictateButton extends StatefulWidget {
  const HoldToDictateButton({
    required this.status,
    required this.onHoldStart,
    required this.onHoldEnd,
    this.levels = const [],
    this.invite = false,
    super.key,
  });

  final DictationStatus status;
  final VoidCallback onHoldStart;
  final VoidCallback onHoldEnd;

  /// Recent input levels, oldest first, shown while recording.
  final List<double> levels;

  /// Breathe a ring to draw the eye, until the first dictation.
  final bool invite;

  @override
  State<HoldToDictateButton> createState() => _HoldToDictateButtonState();
}

class _HoldToDictateButtonState extends State<HoldToDictateButton>
    with SingleTickerProviderStateMixin {
  static const _levelBars = 9;

  late final AnimationController _breath = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 2600),
  );
  var _pressed = false;
  var _breathed = false;

  bool get _busy => widget.status == DictationStatus.transcribing;
  bool get _recording => widget.status == DictationStatus.recording;

  String get _label => switch (widget.status) {
    DictationStatus.recording => 'Release to type',
    DictationStatus.transcribing => 'Typing in...',
    _ => 'Hold to dictate',
  };

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _syncBreath();
  }

  @override
  void didUpdateWidget(HoldToDictateButton oldWidget) {
    super.didUpdateWidget(oldWidget);
    _syncBreath();
  }

  void _syncBreath() {
    final breathe =
        widget.invite &&
        !_busy &&
        !_recording &&
        !MediaQuery.disableAnimationsOf(context);
    if (breathe && !_breathed) {
      _breathed = true;
      _breath.repeat(count: 3);
    } else if (!breathe && _breath.isAnimating) {
      _breath
        ..stop()
        ..value = 0;
    }
  }

  @override
  void dispose() {
    _breath.dispose();
    super.dispose();
  }

  void _down(PointerDownEvent _) {
    if (_busy || _recording) return;
    setState(() => _pressed = true);
    HapticFeedback.lightImpact();
    widget.onHoldStart();
  }

  void _up(PointerEvent _) {
    if (!_pressed) return;
    setState(() => _pressed = false);
    HapticFeedback.lightImpact();
    widget.onHoldEnd();
  }

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    final down = _pressed || _recording;
    final levels = widget.levels.length > _levelBars
        ? widget.levels.sublist(widget.levels.length - _levelBars)
        : widget.levels;
    final Widget lead;
    if (_recording) {
      lead = LevelMeter(
        levels: levels,
        color: c.onAccent,
        barCount: _levelBars,
      );
    } else if (_busy) {
      lead = SizedBox(
        width: 20,
        height: 20,
        child: CircularProgressIndicator(strokeWidth: 2.4, color: c.onAccent),
      );
    } else {
      lead = Icon(Icons.mic_none, color: c.onAccent, size: 22);
    }
    return Semantics(
      button: true,
      enabled: !_busy,
      label: _label,
      child: ExcludeSemantics(
        child: Listener(
          onPointerDown: _down,
          onPointerUp: _up,
          onPointerCancel: _up,
          child: AnimatedBuilder(
            animation: _breath,
            builder: (context, child) {
              // The ring goes out over the first 70% of each breath, then rests.
              final ring = Curves.easeOutCubic.transform(
                (_breath.value / 0.7).clamp(0.0, 1.0),
              );
              return DecoratedBox(
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: [
                    if (_breath.isAnimating)
                      BoxShadow(
                        color: c.accent.withValues(alpha: 0.4 * (1 - ring)),
                        spreadRadius: 12 * ring,
                      ),
                  ],
                ),
                child: child,
              );
            },
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 260),
              curve: Curves.easeOutCubic,
              height: _recording ? 72 : 60,
              decoration: BoxDecoration(
                color: down ? c.accentPressed : c.accent,
                borderRadius: BorderRadius.circular(16),
              ),
              transform: down ? Matrix4.diagonal3Values(0.985, 0.985, 1) : null,
              transformAlignment: Alignment.center,
              alignment: Alignment.center,
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  AnimatedSwitcher(
                    duration: const Duration(milliseconds: 160),
                    child: KeyedSubtree(
                      key: ValueKey(widget.status),
                      child: lead,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Text(
                    _label,
                    style: TextStyle(
                      color: c.onAccent,
                      fontSize: 17,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
