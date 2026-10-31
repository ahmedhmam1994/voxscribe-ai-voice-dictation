import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/dictation/domain/dictation_engine.dart';
import 'package:voxscribe_app/features/settings/widgets/settings_group.dart';
import 'package:voxscribe_app/features/termpacks/domain/term_packs.dart';
import 'package:voxscribe_app/features/termpacks/teach_voice_page.dart';
import 'package:voxscribe_app/features/termpacks/term_packs_controller.dart';
import 'package:voxscribe_app/features/texttools/text_tools_controller.dart';

/// Term packs for a field, the spoken formats that go with them, and the way
/// in to Teach your voice.
class TermPacksPage extends StatefulWidget {
  const TermPacksPage({
    required this.packs,
    required this.textTools,
    required this.engine,
    super.key,
  });

  final TermPacksController packs;
  final TextToolsController textTools;
  final DictationEngine engine;

  @override
  State<TermPacksPage> createState() => _TermPacksPageState();
}

class _TermPacksPageState extends State<TermPacksPage> {
  @override
  void initState() {
    super.initState();
    widget.packs.load();
  }

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    final theme = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(title: const Text('Term packs')),
      body: ListenableBuilder(
        listenable: Listenable.merge([widget.packs, widget.textTools]),
        builder: (context, _) {
          final tools = widget.textTools.settings;
          final enabled = tools.enabledPacks;
          return ListView(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
            children: [
              Text(
                'Words for your field, written the way your field writes '
                'them: "mri" becomes MRI, "met formin" becomes metformin, and '
                'a misheard drug name such as "lisinipril" is fixed. Free, '
                'and nothing leaves the phone.',
                style: theme.bodyMedium,
              ),
              const SizedBox(height: 8),
              SettingsGroup(
                label: 'Packs',
                children: [
                  for (final pack in widget.packs.packs)
                    _PackRow(
                      pack: pack,
                      enabled: enabled.contains(pack.id),
                      onChanged: (on) => widget.textTools.setTermPackEnabled(
                        pack.id,
                        enabled: on,
                      ),
                      onRemove: pack.user ? () => _remove(pack) : null,
                    ),
                ],
              ),
              Align(
                alignment: Alignment.centerLeft,
                child: OutlinedButton.icon(
                  onPressed: _import,
                  icon: const Icon(Icons.file_open_outlined, size: 18),
                  label: const Text('Import your own list'),
                ),
              ),
              const SizedBox(height: 4),
              Text(
                'A text file with one term per line, such as a clinic\'s drug '
                'list or your clients\' names. The same files work on Windows.',
                style: theme.bodySmall,
              ),
              const SizedBox(height: 8),
              SettingsGroup(
                label: 'Spoken formats',
                children: [
                  SettingsSwitchRow(
                    title: 'Spoken formats for the packs',
                    subtitle:
                        'Medical: "one twenty over eighty" becomes 120/80, '
                        '"five milligrams twice daily" becomes 5 mg BID. Law: '
                        '"section twelve subsection b" becomes section 12(b). '
                        'Business: "fifty thousand dollars" becomes \$50,000. '
                        'A number only changes next to the word that shows '
                        'what it is.',
                    value: tools.spokenFormats,
                    onChanged: (value) =>
                        widget.textTools.setSpokenFormats(value: value),
                  ),
                ],
              ),
              SettingsGroup(
                label: 'Your voice',
                children: [
                  SettingsRow(
                    title: 'Teach VoxScribe your voice',
                    subtitle:
                        'Read about ten sentences. VoxScribe finds the words '
                        'it mishears in your voice and offers to fix them.',
                    trailing: Icon(Icons.chevron_right, color: c.muted),
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => TeachVoicePage(
                          engine: widget.engine,
                          platform: widget.packs.platform,
                          textTools: widget.textTools,
                        ),
                      ),
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

  Future<void> _import() async {
    final messenger = ScaffoldMessenger.of(context);
    final message = await widget.packs.importPack(askName: _askName);
    if (message != null) {
      messenger.showSnackBar(SnackBar(content: Text(message)));
    }
  }

  Future<String?> _askName() {
    final name = TextEditingController(text: 'My pack');
    return showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Name this pack'),
        content: TextField(
          controller: name,
          autofocus: true,
          decoration: const InputDecoration(labelText: 'Name'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(name.text),
            child: const Text('Add'),
          ),
        ],
      ),
    ).whenComplete(name.dispose);
  }

  Future<void> _remove(TermPack pack) async {
    if (widget.textTools.settings.enabledPacks.contains(pack.id)) {
      await widget.textTools.setTermPackEnabled(pack.id, enabled: false);
    }
    await widget.packs.remove(pack);
  }
}

class _PackRow extends StatelessWidget {
  const _PackRow({
    required this.pack,
    required this.enabled,
    required this.onChanged,
    required this.onRemove,
  });

  final TermPack pack;
  final bool enabled;
  final ValueChanged<bool> onChanged;
  final VoidCallback? onRemove;

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    final count = '${pack.count} term${pack.count == 1 ? '' : 's'}';
    final remove = onRemove;
    return SettingsRow(
      title: pack.label,
      subtitle: pack.user ? 'Your list, $count' : count,
      onTap: () => onChanged(!enabled),
      trailing: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (remove != null)
            IconButton(
              onPressed: remove,
              tooltip: 'Remove ${pack.label}',
              icon: Icon(Icons.delete_outline, color: c.muted),
            ),
          Switch(value: enabled, onChanged: onChanged),
        ],
      ),
    );
  }
}
