import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';

/// The VoxScribe mark: three sound bars that turn into a text cursor. Same
/// shapes as the launcher icon (res/drawable/ic_launcher_foreground.xml).
class BrandMark extends StatelessWidget {
  const BrandMark({this.height = 20, super.key});

  final double height;

  @override
  Widget build(BuildContext context) {
    return ExcludeSemantics(
      child: CustomPaint(
        size: Size(height * MarkShape.width / MarkShape.height, height),
        painter: _MarkPainter(context.vox.accentInk),
      ),
    );
  }
}

/// The mark's shapes in the 108 unit grid of the launcher icon, relative to
/// its centre (54, 54), so the intro splash can animate the same parts.
abstract final class MarkShape {
  /// Bar centres (x), heights and width.
  static const barX = [-26.0, -12.0, 2.0];
  static const barHeights = [20.0, 36.0, 20.0];
  static const barWidth = 8.0;

  /// The cursor: stem centre (x), stem size, cap width and height.
  static const cursorX = 19.5;
  static const stemWidth = 7.0;
  static const cursorHeight = 56.0;
  static const capWidth = 21.0;
  static const capHeight = 6.0;

  /// The whole mark's size.
  static const width = 60.0;
  static const height = 56.0;

  /// The bars, scaled by [scale] around [center]; [grow] (0 to 1 each)
  /// shrinks a bar while it animates in.
  static List<RRect> bars(Offset center, double scale, [List<double>? grow]) {
    return [
      for (var i = 0; i < barX.length; i++)
        if ((grow?[i] ?? 1) > 0)
          RRect.fromRectAndRadius(
            Rect.fromCenter(
              center: Offset(center.dx + barX[i] * scale, center.dy),
              width: barWidth * scale,
              height:
                  (barHeights[i] * (grow?[i] ?? 1)).clamp(barWidth, 99) * scale,
            ),
            Radius.circular(barWidth * scale / 2),
          ),
    ];
  }

  /// The cursor's stem and caps, scaled by [scale] around [center].
  static List<RRect> cursor(Offset center, double scale) {
    final x = center.dx + cursorX * scale;
    final half = cursorHeight / 2 * scale;
    final cap = Radius.circular(capHeight * scale / 2);
    RRect capAt(double y) => RRect.fromRectAndRadius(
      Rect.fromCenter(
        center: Offset(x, y),
        width: capWidth * scale,
        height: capHeight * scale,
      ),
      cap,
    );
    return [
      RRect.fromRectAndRadius(
        Rect.fromCenter(
          center: Offset(x, center.dy),
          width: stemWidth * scale,
          height: (cursorHeight - capHeight) * scale,
        ),
        Radius.zero,
      ),
      capAt(center.dy - half + capHeight * scale / 2),
      capAt(center.dy + half - capHeight * scale / 2),
    ];
  }
}

class _MarkPainter extends CustomPainter {
  _MarkPainter(this.color);

  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final scale = size.height / MarkShape.height;
    // The mark's centre sits 54 units from its left edge (24) in the grid.
    final center = Offset(30 * scale, size.height / 2);
    final paint = Paint()..color = color;
    for (final shape in [
      ...MarkShape.bars(center, scale),
      ...MarkShape.cursor(center, scale),
    ]) {
      canvas.drawRRect(shape, paint);
    }
  }

  @override
  bool shouldRepaint(_MarkPainter old) => old.color != color;
}
