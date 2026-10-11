import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/pro/pro_controller.dart';
import 'package:voxscribe_app/features/settings/widgets/settings_group.dart';
import 'package:voxscribe_app/features/snippets/snippets_controller.dart';
import 'package:voxscribe_app/features/snippets/snippets_page.dart';
import 'package:voxscribe_app/shared/widgets/vox_card.dart';

/// Shows whether Pro is on. Locked, it takes the license key; unlocked, it
/// opens the Pro features.
class ProPage extends StatefulWidget {
  const ProPage({required this.pro, required this.snippets, super.key});

  final ProController pro;
  final SnippetsController snippets;

  @override
  State<ProPage> createState() => _ProPageState();
}

class _ProPageState extends State<ProPage> {
  final _key = TextEditingController();

  @override
  void dispose() {
    _key.dispose();
    super.dispose();
  }

  void _openSnippets() {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => SnippetsPage(controller: widget.snippets),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('VoxScribe Pro')),
      body: ListenableBuilder(
        listenable: widget.pro,
        builder: (context, _) {
          return ListView(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
            children: widget.pro.isPro ? _unlocked(context) : _locked(context),
          );
        },
      ),
    );
  }

  List<Widget> _unlocked(BuildContext context) {
    return [
      VoxCard(
        child: Row(
          children: [
            Icon(Icons.check_circle, color: context.vox.accentInk),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                'Pro is on. Thank you for supporting VoxScribe.',
                style: Theme.of(context).textTheme.bodyLarge,
              ),
            ),
          ],
        ),
      ),
      SettingsGroup(
        label: 'Pro features',
        children: [
          SettingsRow(
            title: 'Snippets',
            subtitle: 'Say a short phrase, get the full text typed.',
            trailing: const Icon(Icons.chevron_right),
            onTap: _openSnippets,
          ),
        ],
      ),
      SettingsGroup(
        label: 'License',
        children: [
          SettingsRow(
            title: 'Remove license from this phone',
            subtitle: 'Pro turns off here. Your key still works on Windows.',
            titleColor: context.vox.red,
            onTap: widget.pro.deactivate,
          ),
        ],
      ),
    ];
  }

  List<Widget> _locked(BuildContext context) {
    final theme = Theme.of(context).textTheme;
    final error = widget.pro.errorMessage;
    return [
      Text('One key for Windows and this phone.', style: theme.titleLarge),
      const SizedBox(height: 8),
      Text(
        'Pro adds snippets here: say a short phrase and the full text is '
        'typed. If you already bought Pro for Windows, paste the same key.',
        style: theme.bodyMedium,
      ),
      const SizedBox(height: 20),
      TextField(
        controller: _key,
        enabled: !widget.pro.busy,
        autocorrect: false,
        enableSuggestions: false,
        textCapitalization: TextCapitalization.characters,
        decoration: const InputDecoration(labelText: 'License key'),
      ),
      if (error != null) ...[
        const SizedBox(height: 10),
        Text(error, style: theme.bodySmall?.copyWith(color: context.vox.red)),
      ],
      const SizedBox(height: 16),
      FilledButton(
        onPressed: widget.pro.busy
            ? null
            : () => widget.pro.activate(_key.text),
        style: FilledButton.styleFrom(
          minimumSize: const Size.fromHeight(52),
          backgroundColor: context.vox.accent,
          foregroundColor: context.vox.onAccent,
        ),
        child: Text(widget.pro.busy ? 'Checking...' : 'Unlock Pro'),
      ),
      const SizedBox(height: 8),
      TextButton(
        onPressed: widget.pro.openPurchasePage,
        child: const Text('Get a key'),
      ),
    ];
  }
}
