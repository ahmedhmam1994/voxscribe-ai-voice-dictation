import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';

/// A text box to try the floating button on before using it in other apps.
/// The button only shows while a text box has the keyboard open, so a new
/// user who turns it on sees nothing until they type somewhere; this gives
/// them that somewhere, with the steps next to it.
class PracticeCard extends StatefulWidget {
  const PracticeCard({required this.onDone, super.key});

  /// Done after it worked, or Skip.
  final VoidCallback onDone;

  @override
  State<PracticeCard> createState() => _PracticeCardState();
}

class _PracticeCardState extends State<PracticeCard> {
  final _text = TextEditingController();

  @override
  void initState() {
    super.initState();
    _text.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    final theme = Theme.of(context).textTheme;
    final worked = _text.text.trim().isNotEmpty;
    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      padding: const EdgeInsets.fromLTRB(16, 14, 12, 10),
      decoration: BoxDecoration(
        color: c.card,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: c.accent.withValues(alpha: 0.6)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                worked ? Icons.check_circle_outline : Icons.mic_none,
                color: c.accentInk,
                size: 22,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  worked ? 'It works' : 'Try it here first',
                  style: theme.titleMedium,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            worked
                ? 'Now do the same in WhatsApp, Gmail or any app: tap a text '
                      'box, hold the green button, talk, let go.'
                : '1. Tap the box below. The green button appears above your '
                      'keyboard.\n'
                      '2. Hold it and say "Hello, this is my first try".\n'
                      '3. Let go. Your words are typed in the box.',
            style: theme.bodyMedium?.copyWith(color: c.muted, height: 1.4),
          ),
          const SizedBox(height: 10),
          TextField(
            controller: _text,
            minLines: 2,
            maxLines: 4,
            decoration: InputDecoration(
              hintText: 'Tap here, then hold the green button',
              filled: true,
              fillColor: c.background,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: BorderSide(color: c.border),
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: BorderSide(color: c.border),
              ),
            ),
          ),
          const SizedBox(height: 4),
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              if (!worked)
                TextButton(
                  onPressed: widget.onDone,
                  child: Text('Skip', style: TextStyle(color: c.muted)),
                ),
              if (worked)
                FilledButton(
                  onPressed: widget.onDone,
                  style: FilledButton.styleFrom(
                    backgroundColor: c.accent,
                    foregroundColor: c.onAccent,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  child: const Text('Done'),
                ),
            ],
          ),
        ],
      ),
    );
  }
}
