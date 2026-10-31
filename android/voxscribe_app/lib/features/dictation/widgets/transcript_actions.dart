import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';

/// Copy, Fix a word, Listen and Clear for the current transcript.
class TranscriptActions extends StatelessWidget {
  const TranscriptActions({
    required this.onCopy,
    required this.onFixWord,
    required this.onClear,
    this.onListen,
    super.key,
  });

  final VoidCallback? onCopy;
  final VoidCallback? onFixWord;
  final VoidCallback? onClear;

  /// Reads the transcript aloud. Null hides the button.
  final VoidCallback? onListen;

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    return Row(
      children: [
        Expanded(
          child: OutlinedButton.icon(
            onPressed: onCopy,
            icon: const Icon(Icons.copy_outlined, size: 18),
            label: _label('Copy'),
            style: _style(foreground: c.text, border: c.border),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: TextButton.icon(
            onPressed: onFixWord,
            icon: const Icon(Icons.spellcheck, size: 18),
            label: _label('Fix a word'),
            style: _style(foreground: c.accentInk),
          ),
        ),
        if (onListen case final listen?) ...[
          const SizedBox(width: 8),
          Expanded(
            child: TextButton.icon(
              onPressed: onCopy == null ? null : listen,
              icon: const Icon(Icons.volume_up_outlined, size: 18),
              label: _label('Listen'),
              style: _style(foreground: c.accentInk),
            ),
          ),
          const SizedBox(width: 4),
          IconButton(
            onPressed: onClear,
            tooltip: 'Clear',
            icon: const Icon(Icons.delete_outline),
            color: c.muted,
            constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
          ),
        ] else ...[
          const SizedBox(width: 8),
          Expanded(
            child: TextButton.icon(
              onPressed: onClear,
              icon: const Icon(Icons.delete_outline, size: 18),
              label: _label('Clear'),
              style: _style(foreground: c.muted),
            ),
          ),
        ],
      ],
    );
  }

  /// One line, shrunk to fit rather than broken mid-word with large text.
  Widget _label(String text) => FittedBox(
    fit: BoxFit.scaleDown,
    child: Text(text, maxLines: 1, softWrap: false),
  );

  ButtonStyle _style({required Color foreground, Color? border}) {
    return ButtonStyle(
      minimumSize: const WidgetStatePropertyAll(Size.fromHeight(48)),
      padding: const WidgetStatePropertyAll(
        EdgeInsets.symmetric(horizontal: 8),
      ),
      foregroundColor: WidgetStatePropertyAll(foreground),
      textStyle: const WidgetStatePropertyAll(
        TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
      ),
      shape: WidgetStatePropertyAll(
        RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
      side: border == null
          ? null
          : WidgetStatePropertyAll(BorderSide(color: border)),
    );
  }
}
