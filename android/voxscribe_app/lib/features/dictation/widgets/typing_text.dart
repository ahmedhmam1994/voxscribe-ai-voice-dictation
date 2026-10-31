import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';

/// Shows [text] and, whenever it changes, lands it word by word: each word
/// fades up from nothing while the next few follow, with a cursor after the
/// newest. Words keep their place from the start, so the lines never reflow.
/// With reduced motion on, the text simply appears.
class TypingText extends StatefulWidget {
  const TypingText(this.text, {super.key});

  final String text;

  @override
  State<TypingText> createState() => _TypingTextState();
}

class _TypingTextState extends State<TypingText>
    with SingleTickerProviderStateMixin {
  static const _perWord = Duration(milliseconds: 55);

  /// How many words are fading in at once.
  static const _fadeWords = 3;

  late final AnimationController _controller = AnimationController(vsync: this);
  late List<String> _words = _split(widget.text);

  /// Words with the space after them, so joining them gives back the text.
  static List<String> _split(String text) =>
      RegExp(r'\s*\S+\s*').allMatches(text).map((m) => m.group(0)!).toList();

  @override
  void initState() {
    super.initState();
    // Arriving fresh (a new dictation) types in; otherwise it is just shown.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _restart();
    });
  }

  @override
  void didUpdateWidget(TypingText oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.text != widget.text) {
      _words = _split(widget.text);
      _restart();
    }
  }

  void _restart() {
    if (MediaQuery.disableAnimationsOf(context) || _words.isEmpty) {
      _controller.value = 1;
      return;
    }
    _controller
      ..duration = _perWord * (_words.length + _fadeWords)
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
    final color = style?.color ?? context.vox.text;
    return Semantics(
      label: widget.text,
      child: ExcludeSemantics(
        child: AnimatedBuilder(
          animation: _controller,
          builder: (context, _) {
            final progress = _controller.value * (_words.length + _fadeWords);
            final typing = _controller.isAnimating;
            final spans = <InlineSpan>[];
            for (var i = 0; i < _words.length; i++) {
              final shown = ((progress - i) / _fadeWords).clamp(0.0, 1.0);
              spans.add(
                TextSpan(
                  text: _words[i],
                  style: TextStyle(color: color.withValues(alpha: shown)),
                ),
              );
              final newest = i + 1 >= _words.length || progress < i + 1;
              if (typing && newest) {
                spans.add(_caret(context));
                // The rest still take their space, invisible, so nothing reflows.
                for (var j = i + 1; j < _words.length; j++) {
                  spans.add(
                    TextSpan(
                      text: _words[j],
                      style: const TextStyle(color: Colors.transparent),
                    ),
                  );
                }
                break;
              }
            }
            return Text.rich(TextSpan(children: spans), style: style);
          },
        ),
      ),
    );
  }

  WidgetSpan _caret(BuildContext context) {
    return WidgetSpan(
      alignment: PlaceholderAlignment.middle,
      child: Container(
        width: 2,
        height: 20,
        margin: const EdgeInsets.symmetric(horizontal: 1),
        color: context.vox.accentInk,
      ),
    );
  }
}
