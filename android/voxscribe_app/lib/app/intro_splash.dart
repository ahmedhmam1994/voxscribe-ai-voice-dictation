import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:voxscribe_app/shared/widgets/brand_mark.dart';

/// A short animated intro that plays over the app while it loads underneath,
/// then fades away. A tap skips it. The first frame matches the native launch
/// background, so there is no black or white flash before it.
class IntroSplash extends StatefulWidget {
  const IntroSplash({required this.child, this.enabled = true, super.key});

  final Widget child;
  final bool enabled;

  @override
  State<IntroSplash> createState() => _IntroSplashState();
}

class _IntroSplashState extends State<IntroSplash>
    with SingleTickerProviderStateMixin {
  static const _background = Color(0xFF121319);
  static const _accent = Color(0xFF3ECF8E);

  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 2800),
  );
  bool _done = false;
  // The app underneath is built only once the logo has grown, so building it
  // cannot make the opening of the animation stutter.
  bool _mountChild = false;
  // Android's "Remove animations": show the settled logo and just fade through.
  late final bool _calm = WidgetsBinding
      .instance
      .platformDispatcher
      .accessibilityFeatures
      .disableAnimations;

  @override
  void initState() {
    super.initState();
    if (!widget.enabled) {
      _done = true;
      return;
    }
    _controller
      ..addListener(() {
        if (!_mountChild && _controller.value >= 0.45 && mounted) {
          setState(() => _mountChild = true);
        }
      })
      ..addStatusListener((status) {
        if (status == AnimationStatus.completed && mounted) {
          setState(() => _done = true);
        }
      })
      ..forward(from: _calm ? 0.74 : 0);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _skip() {
    if (_done) return;
    // Jump to the fade-out so a tap still ends smoothly.
    if (_controller.value < 0.82) {
      _controller.animateTo(0.82, duration: Duration.zero);
    }
    _controller.animateTo(1, duration: const Duration(milliseconds: 250));
  }

  @override
  Widget build(BuildContext context) {
    if (_done) return widget.child;
    return Stack(
      fit: StackFit.expand,
      children: [
        if (_mountChild || _calm) widget.child,
        AnimatedBuilder(
          animation: _controller,
          builder: (context, _) {
            final t = _controller.value;
            final fade = 1 - ((t - 0.82) / 0.18).clamp(0.0, 1.0);
            return IgnorePointer(
              ignoring: fade == 0,
              child: GestureDetector(
                behavior: HitTestBehavior.opaque,
                onTap: _skip,
                child: Opacity(
                  opacity: fade,
                  child: Semantics(
                    label: 'VoxScribe',
                    child: CustomPaint(
                      painter: _IntroPainter(t, calm: _calm),
                      child: const SizedBox.expand(),
                    ),
                  ),
                ),
              ),
            );
          },
        ),
      ],
    );
  }
}

class _IntroPainter extends CustomPainter {
  _IntroPainter(this.t, {required this.calm});

  final double t;
  final bool calm;

  // Confident arrival, no bounce.
  static const _arrive = Cubic(0.16, 1, 0.3, 1);

  double _ease(double v) => Curves.easeOutCubic.transform(v.clamp(0.0, 1.0));

  double _span(double from, double to) =>
      ((t - from) / (to - from)).clamp(0.0, 1.0);

  @override
  void paint(Canvas canvas, Size size) {
    const bg = _IntroSplashState._background;
    const accent = _IntroSplashState._accent;
    canvas.drawRect(Offset.zero & size, Paint()..color = bg);

    final unit = math.min(size.width, size.height);
    final center = Offset(size.width / 2, size.height * 0.42);
    final scale = unit * 0.30 / MarkShape.height;

    // Glow that swells as the bars come alive.
    final glow = _ease(_span(0.05, 0.4));
    canvas.drawCircle(
      center,
      unit * 0.5,
      Paint()
        ..shader = RadialGradient(
          colors: [
            accent.withValues(alpha: 0.2 * glow),
            accent.withValues(alpha: 0),
          ],
        ).createShader(Rect.fromCircle(center: center, radius: unit * 0.5)),
    );

    // The bars grow from nothing with a small overshoot, left to right, and
    // pulse like live audio; then the text cursor appears and blinks once:
    // voice turning into typed words. Everything settles on the true logo.
    final pulse = _span(0.4, 0.74);
    final settle = 1 - _ease(_span(0.62, 0.78));
    final grow = [
      for (var i = 0; i < MarkShape.barX.length; i++)
        _arrive.transform(_span(0.04 + i * 0.07, 0.40 + i * 0.07)) *
            (!calm && pulse > 0 && pulse < 1
                ? 1 + 0.32 * settle * math.sin(pulse * 17 + i * 1.7)
                : 1.0),
    ];
    final paint = Paint()..color = accent;
    for (final bar in MarkShape.bars(center, scale, grow)) {
      canvas.drawRRect(bar, paint);
    }
    final appear = _ease(_span(0.36, 0.5));
    final blink = !calm && t > 0.6 && t < 0.68 ? 0.25 : 1.0;
    if (appear > 0) {
      final cursorPaint = Paint()
        ..color = accent.withValues(alpha: appear * blink);
      for (final part in MarkShape.cursor(center, scale)) {
        canvas.drawRRect(part, cursorPaint);
      }
    }

    _text(
      canvas,
      'VoxScribe',
      Offset(center.dx, size.height * 0.64),
      fontSize: unit * 0.092,
      weight: FontWeight.w700,
      color: Colors.white,
      progress: _span(0.5, 0.68),
      spacing: -0.5,
    );
    _text(
      canvas,
      'Whisper in, words out.',
      Offset(center.dx, size.height * 0.64 + unit * 0.105),
      fontSize: unit * 0.04,
      weight: FontWeight.w500,
      color: accent,
      progress: _span(0.58, 0.76),
      spacing: 0.4,
    );
  }

  void _text(
    Canvas canvas,
    String text,
    Offset anchor, {
    required double fontSize,
    required FontWeight weight,
    required Color color,
    required double progress,
    required double spacing,
  }) {
    if (progress <= 0) return;
    final eased = _ease(progress);
    final painter = TextPainter(
      text: TextSpan(
        text: text,
        style: TextStyle(
          fontFamily: 'Inter',
          color: color.withValues(alpha: eased),
          fontSize: fontSize,
          fontWeight: weight,
          letterSpacing: spacing,
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    painter.paint(
      canvas,
      Offset(
        anchor.dx - painter.width / 2,
        anchor.dy - painter.height / 2 + (1 - eased) * 14,
      ),
    );
  }

  @override
  bool shouldRepaint(_IntroPainter old) => old.t != t || old.calm != calm;
}
