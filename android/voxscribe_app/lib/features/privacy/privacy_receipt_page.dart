import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/privacy/network_log.dart';
import 'package:voxscribe_app/shared/widgets/vox_card.dart';

/// Every time VoxScribe went online from this phone: what for, where to and
/// what it sent. Proof, on the phone itself, that dictations never leave it.
class PrivacyReceiptPage extends StatefulWidget {
  const PrivacyReceiptPage({
    this.log = const MethodChannelNetworkLog(),
    super.key,
  });

  final NetworkLog log;

  @override
  State<PrivacyReceiptPage> createState() => _PrivacyReceiptPageState();
}

class _PrivacyReceiptPageState extends State<PrivacyReceiptPage> {
  late final Future<List<NetworkLogEntry>> _entries = widget.log.entries();

  static const _months = [
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Aug',
    'Sep',
    'Oct',
    'Nov',
    'Dec',
  ];

  static String _when(DateTime at) {
    String two(int n) => n.toString().padLeft(2, '0');
    return '${at.day} ${_months[at.month - 1]} ${at.year}, '
        '${two(at.hour)}:${two(at.minute)}';
  }

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    final theme = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(title: const Text('Privacy receipt')),
      body: FutureBuilder<List<NetworkLogEntry>>(
        future: _entries,
        builder: (context, snapshot) {
          final entries = snapshot.data ?? const <NetworkLogEntry>[];
          return ListView(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
            children: [
              VoxCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Never sent',
                      style: theme.labelLarge?.copyWith(color: c.accent),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      'Your voice, your dictations, your history and your '
                      'word lists. They are turned into text and kept on '
                      'this phone.',
                      style: theme.bodyLarge,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 20),
              Text(
                'Everything VoxScribe sent from this phone',
                style: theme.titleMedium,
              ),
              const SizedBox(height: 4),
              Text(
                'Written down here as it happens, and kept on the phone. If '
                'the built-in speech model is off, the phone may fall back to '
                'Google speech recognition, which can use the internet. That '
                'is not VoxScribe and is not listed here.',
                style: theme.bodySmall?.copyWith(color: c.muted),
              ),
              const SizedBox(height: 12),
              if (snapshot.connectionState == ConnectionState.done &&
                  entries.isEmpty)
                Text(
                  'Nothing yet. VoxScribe has not gone online from this '
                  'phone since this receipt started.',
                  style: theme.bodyMedium,
                ),
              for (final entry in entries)
                _EntryTile(entry: entry, when: _when(entry.at)),
            ],
          );
        },
      ),
    );
  }
}

class _EntryTile extends StatelessWidget {
  const _EntryTile({required this.entry, required this.when});

  final NetworkLogEntry entry;
  final String when;

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    final theme = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: VoxCard(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(child: Text(entry.what, style: theme.titleSmall)),
                Text(when, style: theme.bodySmall?.copyWith(color: c.muted)),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              'To ${entry.host}',
              style: theme.bodySmall?.copyWith(color: c.muted),
            ),
            const SizedBox(height: 4),
            Text('Sent: ${entry.sent}', style: theme.bodyMedium),
          ],
        ),
      ),
    );
  }
}
