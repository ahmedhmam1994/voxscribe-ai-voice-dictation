import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/core/formatting.dart';
import 'package:voxscribe_app/features/history/domain/dictation_entry.dart';

/// Today's dictations, newest first. A dictation that has only just been
/// made fades and slides in; older ones are simply there.
class TodayList extends StatelessWidget {
  const TodayList({
    required this.entries,
    this.onFixWord,
    this.clock = DateTime.now,
    super.key,
  });

  final List<DictationEntry> entries;

  /// Opens the "Fix a word" sheet for an entry's text. Null hides the button.
  final void Function(String text)? onFixWord;

  /// The current time. Replaced in tests.
  final DateTime Function() clock;

  /// How recent an entry must be to count as "just made" and fade in.
  static const freshFor = Duration(seconds: 10);

  @override
  Widget build(BuildContext context) {
    if (entries.isEmpty) {
      return Text(
        'No dictations yet today.',
        style: Theme.of(context).textTheme.bodyMedium
            ?.copyWith(color: context.vox.muted),
      );
    }
    return Column(
      children: [
        for (var i = 0; i < entries.length; i++)
          _FadeInOnce(
            // Keyed by the entry, so a row that is already shown keeps its
            // state and does not fade in again when a new one arrives.
            key: ValueKey(entries[i].createdAt),
            animate: clock().difference(entries[i].createdAt) < freshFor,
            child: _EntryRow(
              entry: entries[i],
              showDivider: i > 0,
              onFixWord: onFixWord,
            ),
          ),
      ],
    );
  }
}

class _EntryRow extends StatelessWidget {
  const _EntryRow({
    required this.entry,
    required this.showDivider,
    required this.onFixWord,
  });

  final DictationEntry entry;
  final bool showDivider;
  final void Function(String text)? onFixWord;

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    final theme = Theme.of(context).textTheme;
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 14),
      decoration: BoxDecoration(
        border: showDivider
            ? Border(top: BorderSide(color: c.softBorder))
            : null,
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 74,
            child: Text(formatClock(entry.createdAt), style: theme.bodySmall),
          ),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(entry.text, style: theme.bodyMedium),
                const SizedBox(height: 4),
                Text(
                  '${formatWordCount(entry.wordCount)}, '
                  '${formatSeconds(entry.duration)}',
                  style: theme.bodySmall?.copyWith(fontSize: 12),
                ),
                if (onFixWord != null)
                  TextButton.icon(
                    onPressed: () => onFixWord!(entry.text),
                    icon: const Icon(Icons.spellcheck, size: 16),
                    label: const Text('Fix a word'),
                    style: TextButton.styleFrom(
                      foregroundColor: c.accentInk,
                      padding: const EdgeInsets.symmetric(horizontal: 0),
                      minimumSize: const Size(0, 36),
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Fades and slides its child in once, when first shown, if [animate] is on
/// and reduced motion is off.
class _FadeInOnce extends StatefulWidget {
  const _FadeInOnce({required this.animate, required this.child, super.key});

  final bool animate;
  final Widget child;

  @override
  State<_FadeInOnce> createState() => _FadeInOnceState();
}

class _FadeInOnceState extends State<_FadeInOnce>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 360),
  );
  late final Animation<double> _curve = CurvedAnimation(
    parent: _controller,
    curve: Curves.easeOutCubic,
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_controller.isAnimating || _controller.isCompleted) return;
    if (widget.animate && !MediaQuery.disableAnimationsOf(context)) {
      _controller.forward();
    } else {
      _controller.value = 1;
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _curve,
      child: SlideTransition(
        position: Tween(
          begin: const Offset(0, -0.15),
          end: Offset.zero,
        ).animate(_curve),
        child: widget.child,
      ),
    );
  }
}
