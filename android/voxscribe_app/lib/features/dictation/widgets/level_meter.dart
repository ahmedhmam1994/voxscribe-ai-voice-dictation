import 'package:flutter/material.dart';

/// A row of bars showing recent input levels (each 0 to 1).
class LevelMeter extends StatelessWidget {
  const LevelMeter({
    required this.levels,
    required this.color,
    required this.barCount,
    super.key,
  });

  static const double _barWidth = 3;
  static const double _gap = 2;
  static const double _minHeight = 4;
  static const double _maxHeight = 18;

  final List<double> levels;
  final Color color;
  final int barCount;

  @override
  Widget build(BuildContext context) {
    return ExcludeSemantics(
      child: CustomPaint(
        size: Size(barCount * (_barWidth + _gap), _maxHeight),
        painter: _LevelMeterPainter(levels: levels, color: color),
      ),
    );
  }
}

class _LevelMeterPainter extends CustomPainter {
  _LevelMeterPainter({required this.levels, required this.color});

  final List<double> levels;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = color;
    for (var i = 0; i < levels.length; i++) {
      final height =
          LevelMeter._minHeight +
          (LevelMeter._maxHeight - LevelMeter._minHeight) * levels[i];
      final left = i * (LevelMeter._barWidth + LevelMeter._gap);
      final top = (size.height - height) / 2;
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTWH(left, top, LevelMeter._barWidth, height),
          const Radius.circular(2),
        ),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(_LevelMeterPainter oldDelegate) =>
      oldDelegate.levels != levels || oldDelegate.color != color;
}
