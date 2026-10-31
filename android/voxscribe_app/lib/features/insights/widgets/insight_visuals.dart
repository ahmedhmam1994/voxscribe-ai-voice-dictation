import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';

/// The last seven days as small squares, oldest first, lit where something
/// was dictated. They light up one after another when first shown.
class DayDots extends StatefulWidget {
  const DayDots({required this.active, super.key});

  final List<bool> active;

  @override
  State<DayDots> createState() => _DayDotsState();
}

class _DayDotsState extends State<DayDots> with SingleTickerProviderStateMixin {
  late final AnimationController _light = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1100),
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_light.isAnimating || _light.isCompleted) return;
    if (MediaQuery.disableAnimationsOf(context)) {
      _light.value = 1;
    } else {
      _light.forward();
    }
  }

  @override
  void dispose() {
    _light.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    return ExcludeSemantics(
      child: AnimatedBuilder(
        animation: _light,
        builder: (context, _) => Row(
          children: [
            for (var i = 0; i < widget.active.length; i++) ...[
              if (i > 0) const SizedBox(width: 5),
              _dot(c, i),
            ],
          ],
        ),
      ),
    );
  }

  Widget _dot(VoxColors c, int i) {
    final start = 0.25 + i * 0.08;
    final t = widget.active[i]
        ? Interval(
            start,
            start + 0.2,
            curve: Curves.easeOutBack,
          ).transform(_light.value)
        : 0.0;
    return Transform.scale(
      scale: 1 + 0.1 * t,
      child: Container(
        width: 14,
        height: 14,
        decoration: BoxDecoration(
          color: Color.lerp(c.raised, c.accent, t.clamp(0.0, 1.0)),
          borderRadius: BorderRadius.circular(4),
        ),
      ),
    );
  }
}

/// A dictation drawn as a strip of its own words: one bar per word, as tall as
/// the word is long. It wipes in from the left when first shown.
class WordStrip extends StatelessWidget {
  const WordStrip({required this.text, super.key});

  final String text;

  @override
  Widget build(BuildContext context) {
    final still = MediaQuery.disableAnimationsOf(context);
    final words = text.split(RegExp(r'\s+')).where((w) => w.isNotEmpty);
    final lengths = [for (final w in words) w.length];
    return ExcludeSemantics(
      child: TweenAnimationBuilder<double>(
        tween: Tween(begin: still ? 1 : 0, end: 1),
        duration: still ? Duration.zero : const Duration(milliseconds: 1300),
        curve: Curves.easeOutExpo,
        builder: (context, shown, child) => ClipRect(
          child: Align(
            alignment: Alignment.centerLeft,
            widthFactor: shown,
            child: child,
          ),
        ),
        child: CustomPaint(
          size: const Size(double.infinity, 26),
          painter: _WordStripPainter(lengths, context.vox.accent),
        ),
      ),
    );
  }
}

class _WordStripPainter extends CustomPainter {
  _WordStripPainter(this.lengths, this.color);

  static const double _bar = 3;
  static const double _gap = 2;

  final List<int> lengths;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = color;
    final fits = (size.width / (_bar + _gap)).floor();
    final centerY = size.height / 2;
    for (var i = 0; i < lengths.length && i < fits; i++) {
      final h = 4 + (size.height - 4) * (lengths[i].clamp(1, 10) / 10);
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTWH(i * (_bar + _gap), centerY - h / 2, _bar, h),
          const Radius.circular(1.5),
        ),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(_WordStripPainter oldDelegate) =>
      oldDelegate.lengths != lengths || oldDelegate.color != color;
}
