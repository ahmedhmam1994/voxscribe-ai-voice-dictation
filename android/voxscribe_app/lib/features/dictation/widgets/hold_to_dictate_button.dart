import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/dictation/domain/dictation_status.dart';

/// The big green button. Hold to record, release to transcribe.
class HoldToDictateButton extends StatefulWidget {
  const HoldToDictateButton({
    required this.status,
    required this.onHoldStart,
    required this.onHoldEnd,
    super.key,
  });

  final DictationStatus status;
  final VoidCallback onHoldStart;
  final VoidCallback onHoldEnd;

  @override
  State<HoldToDictateButton> createState() => _HoldToDictateButtonState();
}

class _HoldToDictateButtonState extends State<HoldToDictateButton> {
  var _pressed = false;

  bool get _busy => widget.status == DictationStatus.transcribing;
  bool get _recording => widget.status == DictationStatus.recording;

  String get _label => switch (widget.status) {
    DictationStatus.recording => 'Release to type',
    DictationStatus.transcribing => 'Typing in...',
    _ => 'Hold to dictate',
  };

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
    return Semantics(
      button: true,
      enabled: !_busy,
      label: _label,
      child: ExcludeSemantics(
        child: Listener(
          onPointerDown: _down,
          onPointerUp: _up,
          onPointerCancel: _up,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 80),
            height: 60,
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
                Icon(Icons.mic_none, color: c.onAccent, size: 22),
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
    );
  }
}
