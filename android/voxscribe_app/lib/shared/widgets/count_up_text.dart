import 'package:flutter/material.dart';

/// A number that counts up to [value] when it first appears, and from the old
/// number to the new one when it changes. With reduced motion on, the number
/// simply shows.
class CountUpText extends StatelessWidget {
  const CountUpText({
    required this.value,
    required this.format,
    this.style,
    super.key,
  });

  final int value;

  /// Turns the number being shown into text, for example "12,480" or "3 days".
  final String Function(int value) format;
  final TextStyle? style;

  static const duration = Duration(milliseconds: 700);

  @override
  Widget build(BuildContext context) {
    final still = MediaQuery.disableAnimationsOf(context);
    return Semantics(
      label: format(value),
      child: ExcludeSemantics(
        child: TweenAnimationBuilder<double>(
          tween: Tween(begin: 0, end: value.toDouble()),
          duration: still ? Duration.zero : duration,
          curve: Curves.easeOutCubic,
          builder: (context, shown, _) =>
              Text(format(shown.round()), style: style),
        ),
      ),
    );
  }
}
