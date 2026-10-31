import 'package:flutter/material.dart';

/// A number whose digits roll into place like an odometer: up from zero when
/// it first shows, and from the old digits to the new ones when it changes.
/// Separators such as commas stay put. With reduced motion on, it simply shows.
class RollingNumber extends StatelessWidget {
  const RollingNumber({
    required this.value,
    required this.format,
    this.style,
    super.key,
  });

  final int value;

  /// Turns the number into text, for example "12,480".
  final String Function(int value) format;
  final TextStyle? style;

  @override
  Widget build(BuildContext context) {
    final still = MediaQuery.disableAnimationsOf(context);
    final text = format(value);
    final textStyle = DefaultTextStyle.of(context).style
        .merge(style)
        .copyWith(fontFeatures: const [FontFeature.tabularFigures()]);
    final digit = (TextPainter(
      text: TextSpan(text: '0', style: textStyle),
      textDirection: TextDirection.ltr,
      textScaler: MediaQuery.textScalerOf(context),
    )..layout()).size;
    final chars = text.split('');
    return Semantics(
      label: text,
      child: ExcludeSemantics(
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            for (var i = 0; i < chars.length; i++)
              if (int.tryParse(chars[i]) case final n?)
                _DigitColumn(
                  // Keyed from the right, so the ones column stays the ones
                  // column when the number gains a digit.
                  key: ValueKey(chars.length - i),
                  digit: n,
                  size: digit,
                  style: textStyle,
                  duration: still
                      ? Duration.zero
                      : Duration(milliseconds: 900 + 80 * i),
                )
              else
                Text(chars[i], style: textStyle),
          ],
        ),
      ),
    );
  }
}

class _DigitColumn extends StatelessWidget {
  const _DigitColumn({
    required this.digit,
    required this.size,
    required this.style,
    required this.duration,
    super.key,
  });

  final int digit;
  final Size size;
  final TextStyle style;
  final Duration duration;

  @override
  Widget build(BuildContext context) {
    return SizedBox.fromSize(
      size: size,
      child: ClipRect(
        child: TweenAnimationBuilder<double>(
          tween: Tween(
            begin: duration == Duration.zero ? digit.toDouble() : 0,
            end: digit.toDouble(),
          ),
          duration: duration,
          curve: Curves.easeOutExpo,
          builder: (context, shown, child) => OverflowBox(
            alignment: Alignment.topCenter,
            maxHeight: size.height * 10,
            child: Transform.translate(
              offset: Offset(0, -shown * size.height),
              child: child,
            ),
          ),
          child: Column(
            children: [
              for (var n = 0; n < 10; n++)
                SizedBox.fromSize(
                  size: size,
                  child: Text('$n', style: style, textAlign: TextAlign.center),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
