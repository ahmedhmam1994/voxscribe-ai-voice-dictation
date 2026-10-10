import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';

/// Shows [text] and types it in character by character whenever it changes.
/// With reduced motion on, the text simply appears.
class TypingText extends StatefulWidget {
  const TypingText(this.text, {super.key});

  final String text;

  @override
  State<TypingText> createState() => _TypingTextState();
}

class _TypingTextState extends State<TypingText>
    with SingleTickerProviderStateMixin {
  static const _perCharacter = Duration(milliseconds: 16);

  late final AnimationController _controller = AnimationController(vsync: this);

  @override
  void initState() {
    super.initState();
    _controller.value = 1;
  }

  @override
  void didUpdateWidget(TypingText oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.text != widget.text) _restart();
  }

  void _restart() {
    if (MediaQuery.disableAnimationsOf(context)) {
      _controller.value = 1;
      return;
    }
    _controller
      ..duration = _perCharacter * widget.text.length
      ..forward(from: 0);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final style = Theme.of(context).textTheme.bodyLarge;
    return Semantics(
      label: widget.text,
      child: ExcludeSemantics(
        child: AnimatedBuilder(
          animation: _controller,
          builder: (context, _) {
            final shown = (widget.text.length * _controller.value).floor();
            final typing = _controller.isAnimating;
            return Text.rich(
              TextSpan(
                children: [
                  TextSpan(text: widget.text.substring(0, shown)),
                  if (typing)
                    WidgetSpan(
                      alignment: PlaceholderAlignment.middle,
                      child: Container(
                        width: 2,
                        height: 20,
                        margin: const EdgeInsets.only(left: 2),
                        color: context.vox.accentInk,
                      ),
                    ),
                ],
              ),
              style: style,
            );
          },
        ),
      ),
    );
  }
}
