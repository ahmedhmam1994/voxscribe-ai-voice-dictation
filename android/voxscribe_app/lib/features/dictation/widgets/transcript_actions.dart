import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';

/// Copy and Clear for the current transcript.
class TranscriptActions extends StatelessWidget {
  const TranscriptActions({
    required this.onCopy,
    required this.onClear,
    super.key,
  });

  final VoidCallback? onCopy;
  final VoidCallback? onClear;

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    return Row(
      children: [
        Expanded(
          child: OutlinedButton.icon(
            onPressed: onCopy,
            icon: const Icon(Icons.copy_outlined, size: 18),
            label: const Text('Copy'),
            style: _style(foreground: c.text, border: c.border),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: TextButton.icon(
            onPressed: onClear,
            icon: const Icon(Icons.delete_outline, size: 18),
            label: const Text('Clear'),
            style: _style(foreground: c.muted),
          ),
        ),
      ],
    );
  }

  ButtonStyle _style({required Color foreground, Color? border}) {
    return ButtonStyle(
      minimumSize: const WidgetStatePropertyAll(Size.fromHeight(48)),
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
