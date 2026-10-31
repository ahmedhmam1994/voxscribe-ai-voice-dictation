import 'package:flutter/material.dart';

/// The recording so far as a row of bars, newest on the right, older ones
/// fading out to the left. Each level is 0 to 1; [slots] fixes the bar width,
/// so the row fills in from the right as the recording starts.
class VoiceWaveform extends StatelessWidget {
  const VoiceWaveform({
    required this.levels,
    required this.color,
    required this.slots,
    super.key,
  });

  final List<double> levels;
  final Color color;
  final int slots;

  @override
  Widget build(BuildContext context) {
    return ExcludeSemantics(
      child: CustomPaint(
        size: Size.infinite,
        painter: _WaveformPainter(levels: levels, color: color, slots: slots),
      ),
    );
  }
}

class _WaveformPainter extends CustomPainter {
  _WaveformPainter({
    required this.levels,
    required this.color,
    required this.slots,
  });

  static const double _minHeight = 4;

  final List<double> levels;
  final Color color;
  final int slots;

  @override
  void paint(Canvas canvas, Size size) {
    final slot = size.width / slots;
    final barWidth = slot * 0.62;
    final paint = Paint();
    final centerY = size.height / 2;
    final first = slots - levels.length;
    for (var i = 0; i < levels.length; i++) {
      final height =
          _minHeight + (size.height - _minHeight) * levels[i].clamp(0.0, 1.0);
      final left = (first + i) * slot + (slot - barWidth) / 2;
      // Older bars fade, so the eye follows the newest sound on the right.
      paint.color = color.withValues(alpha: 0.3 + 0.7 * (first + i) / slots);
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTWH(left, centerY - height / 2, barWidth, height),
          Radius.circular(barWidth / 2),
        ),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(_WaveformPainter oldDelegate) =>
      oldDelegate.levels != levels || oldDelegate.color != color;
}
