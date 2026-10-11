import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/settings/widgets/settings_group.dart';
import 'package:voxscribe_app/features/snippets/domain/snippet.dart';
import 'package:voxscribe_app/features/snippets/snippets_controller.dart';
import 'package:voxscribe_app/shared/widgets/vox_card.dart';

/// Lists the snippets and lets the user add, change and delete them.
class SnippetsPage extends StatefulWidget {
  const SnippetsPage({required this.controller, super.key});

  final SnippetsController controller;

  @override
  State<SnippetsPage> createState() => _SnippetsPageState();
}

class _SnippetsPageState extends State<SnippetsPage> {
  @override
  void initState() {
    super.initState();
    widget.controller.load();
  }

  Future<void> _edit([Snippet? existing]) async {
    final result = await showDialog<Snippet>(
      context: context,
      builder: (_) => _SnippetDialog(existing: existing),
    );
    if (result != null) await widget.controller.replace(existing, result);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(title: const Text('Snippets')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _edit,
        backgroundColor: context.vox.accent,
        foregroundColor: context.vox.onAccent,
        icon: const Icon(Icons.add),
        label: const Text('New snippet'),
      ),
      body: ListenableBuilder(
        listenable: widget.controller,
        builder: (context, _) {
          final snippets = widget.controller.snippets;
          return ListView(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 96),
            children: [
              Text(
                'Say a trigger on its own and its text is typed instead. '
                'Use {date} or {time} in the text to fill in the day or hour.',
                style: theme.bodyMedium,
              ),
              const SizedBox(height: 16),
              if (snippets.isEmpty)
                const VoxCard(
                  child: Text(
                    'No snippets yet. Try "my email" as a trigger, with your '
                    'address as the text.',
                  ),
                )
              else
                SettingsGroup(
                  label: 'Your snippets',
                  children: [
                    for (final snippet in snippets)
                      SettingsRow(
                        title: snippet.trigger,
                        subtitle: snippet.expansion,
                        onTap: () => _edit(snippet),
                        trailing: IconButton(
                          tooltip: 'Delete ${snippet.trigger}',
                          icon: const Icon(Icons.delete_outline),
                          onPressed: () => widget.controller.remove(snippet),
                        ),
                      ),
                  ],
                ),
            ],
          );
        },
      ),
    );
  }
}

class _SnippetDialog extends StatefulWidget {
  const _SnippetDialog({this.existing});

  final Snippet? existing;

  @override
  State<_SnippetDialog> createState() => _SnippetDialogState();
}

class _SnippetDialogState extends State<_SnippetDialog> {
  late final TextEditingController _trigger = TextEditingController(
    text: widget.existing?.trigger,
  );
  late final TextEditingController _expansion = TextEditingController(
    text: widget.existing?.expansion,
  );

  @override
  void dispose() {
    _trigger.dispose();
    _expansion.dispose();
    super.dispose();
  }

  void _save() {
    final trigger = _trigger.text.trim();
    if (trigger.isEmpty || _expansion.text.isEmpty) return;
    Navigator.of(context)
        .pop(Snippet(trigger: trigger, expansion: _expansion.text));
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.existing == null ? 'New snippet' : 'Edit snippet'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          TextField(
            controller: _trigger,
            autofocus: true,
            textInputAction: TextInputAction.next,
            decoration: const InputDecoration(labelText: 'When I say'),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _expansion,
            minLines: 2,
            maxLines: 5,
            decoration: const InputDecoration(labelText: 'Type this'),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        TextButton(onPressed: _save, child: const Text('Save')),
      ],
    );
  }
}
