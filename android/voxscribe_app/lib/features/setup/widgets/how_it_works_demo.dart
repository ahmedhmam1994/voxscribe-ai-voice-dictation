import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';

/// A short looping picture of the whole idea, shown on the Setup screen: a
/// chat box with the keyboard open, a finger holds the floating button, it
/// shows the mic level, then a wave while it transcribes, a check, and the
/// words appear in the box. With reduced motion on it is a still of the end.
class HowItWorksDemo extends StatefulWidget {
  const HowItWorksDemo({super.key});

  static const text = 'Running ten minutes late, start without me.';

  @override
  State<HowItWorksDemo> createState() => _HowItWorksDemoState();
}

class _HowItWorksDemoState extends State<HowItWorksDemo>
    with SingleTickerProviderStateMixin {
  static const _loop = Duration(milliseconds: 7600);

  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: _loop,
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (MediaQuery.disableAnimationsOf(context)) {
      _controller
        ..stop()
        ..value = _DemoPainter.still / 7.6;
    } else if (!_controller.isAnimating) {
      _controller.repeat();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    return Semantics(
      label:
          'Animation: hold the floating button, talk, and your words are '
          'typed into the text box.',
      child: ExcludeSemantics(
        child: Container(
          height: 204,
          decoration: BoxDecoration(
            color: c.card,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: c.softBorder),
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: AnimatedBuilder(
              animation: _controller,
              builder: (context, _) => CustomPaint(
                painter: _DemoPainter(
                  t: _controller.value * 7.6,
                  colors: c,
                  textStyle: Theme.of(context).textTheme.bodyMedium!,
                ),
                size: Size.infinite,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _DemoPainter extends CustomPainter {
  _DemoPainter({required this.t, required this.colors, required this.textStyle});

  // Timeline of one loop, in seconds.
  static const press = 0.8;
  static const release = 3.0;
  static const typed = 3.9;
  static const typingEnd = 5.5;
  static const loop = 7.6;
  static const still = 6.0;

  final double t;
  final VoxColors colors;
  final TextStyle textStyle;

  static double _ease(double v) {
    final x = v.clamp(0.0, 1.0);
    return 1 - math.pow(1 - x, 3).toDouble();
  }

  @override
  void paint(Canvas canvas, Size size) {
    final c = colors;
    final w = size.width;

    // A chat message bubble from the other person, so it reads as a chat.
    final incoming = RRect.fromRectAndRadius(
      Rect.fromLTWH(16, 14, math.min(190, w * 0.55), 30),
      const Radius.circular(14),
    );
    canvas.drawRRect(incoming, Paint()..color = c.raised);
    _text(canvas, 'Are you on your way?', Offset(28, 21), c.muted, 13);

    // The text box.
    final box = RRect.fromRectAndRadius(
      Rect.fromLTWH(16, 54, w - 32, 40),
      const Radius.circular(20),
    );
    canvas.drawRRect(box, Paint()..color = c.background);
    canvas.drawRRect(
      box,
      Paint()
        ..style = PaintingStyle.stroke
        ..color = c.border,
    );
    final String shown;
    if (t < typed) {
      shown = '';
    } else if (t < typingEnd) {
      final share = (t - typed) / (typingEnd - typed);
      shown = HowItWorksDemo.text.substring(
        0,
        (HowItWorksDemo.text.length * share).floor(),
      );
    } else {
      shown = HowItWorksDemo.text;
    }
    final fade = t > loop - 0.6 ? ((loop - t) / 0.6).clamp(0.0, 1.0) : 1.0;
    final textWidth = shown.isEmpty
        ? 0.0
        : _text(
            canvas,
            shown,
            const Offset(32, 65),
            c.text.withValues(alpha: fade),
            13.5,
            maxWidth: w - 64,
          );
    if (shown.isEmpty) {
      _text(canvas, 'Message', const Offset(32, 65), c.muted, 13.5);
    }
    if ((t * 2) % 2 < 1.2 || (t >= typed && t < typingEnd)) {
      final x = 33 + textWidth;
      canvas.drawLine(
        Offset(x, 64),
        Offset(x, 84),
        Paint()
          ..color = c.accentInk
          ..strokeWidth = 1.6,
      );
    }

    // The top of the keyboard, so the button sits where it really appears.
    final keyboardTop = size.height - 44;
    canvas.drawRect(
      Rect.fromLTWH(0, keyboardTop, w, 44),
      Paint()..color = c.raised,
    );
    final keyPaint = Paint()..color = c.card;
    const keys = 10;
    final keyW = (w - 16) / keys;
    for (var i = 0; i < keys; i++) {
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTWH(8 + i * keyW + 2, keyboardTop + 8, keyW - 4, 28),
          const Radius.circular(5),
        ),
        keyPaint,
      );
    }

    _drawButton(canvas, Offset(w - 46, keyboardTop - 32));
  }

  void _drawButton(Canvas canvas, Offset center) {
    final c = colors;
    final holding = t >= press && t < release;
    final transcribing = t >= release && t < typed;
    final done = t >= typed && t < typed + 0.9;
    final pressScale = holding ? 0.92 : 1.0;
    final radius = 24.0 * pressScale;

    Color fill = c.accent;
    if (holding) fill = c.accentPressed;
    if (transcribing) fill = c.amber;
    canvas.drawCircle(
      center + const Offset(0, 3),
      radius,
      Paint()..color = Colors.black.withValues(alpha: 0.25),
    );
    canvas.drawCircle(center, radius, Paint()..color = fill);
    final ink = Paint()
      ..color = c.onAccent
      ..strokeCap = StrokeCap.round;

    if (holding || transcribing) {
      // Five bars: the live level while held, a slow wave while transcribing.
      for (var i = 0; i < 5; i++) {
        final double value;
        if (holding) {
          final distance = (i - 2).abs();
          final voice =
              (math.sin(t * 7.1 - distance * 0.9)).abs() *
              (0.55 + 0.45 * math.sin(t * 2.3));
          value = math.max(0.12, voice * (1 - 0.18 * distance));
        } else {
          value = 0.25 + 0.35 * (0.5 + 0.5 * math.sin(t * 6 - i * 0.7));
        }
        final h = 4 + value * 18;
        final x = center.dx - 12 + i * 6;
        canvas.drawLine(
          Offset(x, center.dy - h / 2),
          Offset(x, center.dy + h / 2),
          ink..strokeWidth = 3.4,
        );
      }
    } else if (done) {
      final path = Path()
        ..moveTo(center.dx - 8, center.dy + 0.5)
        ..lineTo(center.dx - 2.5, center.dy + 6)
        ..lineTo(center.dx + 8.5, center.dy - 5.5);
      canvas.drawPath(
        path,
        ink
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2.8
          ..strokeJoin = StrokeJoin.round,
      );
    } else {
      // The mic icon.
      final body = RRect.fromRectAndRadius(
        Rect.fromCenter(center: center.translate(0, -3), width: 9, height: 14),
        const Radius.circular(4.5),
      );
      canvas.drawRRect(body, Paint()..color = c.onAccent);
      final stand = Paint()
        ..color = c.onAccent
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2
        ..strokeCap = StrokeCap.round;
      canvas.drawArc(
        Rect.fromCenter(center: center.translate(0, -1), width: 16, height: 16),
        0.2,
        math.pi - 0.4,
        false,
        stand,
      );
      canvas.drawLine(center.translate(0, 7), center.translate(0, 10), stand);
    }

    // A fingertip resting on the button while it is held.
    if (holding) {
      final appear = _ease((t - press) / 0.2);
      canvas.drawCircle(
        center.translate(10, 14),
        15,
        Paint()..color = Colors.white.withValues(alpha: 0.22 * appear),
      );
    }
  }

  double _text(
    Canvas canvas,
    String text,
    Offset at,
    Color color,
    double size, {
    double maxWidth = 400,
  }) {
    final painter = TextPainter(
      text: TextSpan(
        text: text,
        style: textStyle.copyWith(color: color, fontSize: size),
      ),
      textDirection: TextDirection.ltr,
      maxLines: 1,
      ellipsis: '…',
    )..layout(maxWidth: maxWidth);
    painter.paint(canvas, at);
    return painter.width;
  }

  @override
  bool shouldRepaint(_DemoPainter old) => old.t != t || old.colors != colors;
}
