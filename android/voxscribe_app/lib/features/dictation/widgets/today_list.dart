import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/core/formatting.dart';
import 'package:voxscribe_app/features/history/domain/dictation_entry.dart';

/// Today's dictations, newest first.
class TodayList extends StatelessWidget {
  const TodayList({required this.entries, super.key});

  final List<DictationEntry> entries;

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
          _EntryRow(entry: entries[i], showDivider: i > 0),
      ],
    );
  }
}

class _EntryRow extends StatelessWidget {
  const _EntryRow({required this.entry, required this.showDivider});

  final DictationEntry entry;
  final bool showDivider;

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
              ],
            ),
          ),
        ],
      ),
    );
  }
}
