import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/settings/widgets/settings_group.dart';

/// One of the two speech models in Settings: Granite (English and the
/// European languages) or Nemotron (Arabic and the other languages). There is no switch:
/// the language picks the model, and dictation needs that one.
///
/// Hides itself when the phone side is not there (tests, older builds).
class MainModelRow extends StatefulWidget {
  const MainModelRow({
    required this.model,
    required this.title,
    required this.pitch,
    this.inUse = false,
    this.channel,
    super.key,
  });

  /// `english` or `arabic`.
  final String model;
  final String title;

  /// Why to download it, shown before the size.
  final String pitch;

  /// The language you speak uses this model, so removing it stops dictation.
  final bool inUse;
  final MethodChannel? channel;

  @override
  State<MainModelRow> createState() => _MainModelRowState();
}

class _MainModelRowState extends State<MainModelRow> {
  late final MethodChannel _channel =
      widget.channel ?? const MethodChannel('com.voxscribe.android/mainmodels');
  Map<String, Object?>? _status;
  Timer? _poll;
  var _busy = false;

  @override
  void initState() {
    super.initState();
    unawaited(_refresh());
  }

  @override
  void dispose() {
    _poll?.cancel();
    super.dispose();
  }

  Future<void> _refresh() async {
    try {
      final raw = await _channel.invokeMapMethod<String, Object?>('status', {
        'model': widget.model,
      });
      if (!mounted) return;
      setState(() => _status = raw);
      final downloading = raw?['downloading'] == true;
      if (downloading && _poll == null) {
        _poll = Timer.periodic(
          const Duration(milliseconds: 500),
          (_) => unawaited(_refresh()),
        );
      } else if (!downloading) {
        _poll?.cancel();
        _poll = null;
      }
    } on MissingPluginException {
      // No phone side: leave the row hidden.
    } on PlatformException {
      // Same.
    }
  }

  Future<void> _call(String method) async {
    setState(() => _busy = true);
    try {
      await _channel.invokeMethod<void>(method, {'model': widget.model});
    } on PlatformException {
      // The status below carries the reason.
    }
    if (mounted) setState(() => _busy = false);
    await _refresh();
  }

  @override
  Widget build(BuildContext context) {
    final status = _status;
    if (status == null) return const SizedBox.shrink();
    final installed = status['installed'] == true;
    final downloading = status['downloading'] == true;
    final percent = (status['percent'] as num?)?.toInt() ?? 0;
    final megabytes = (status['megabytes'] as num?)?.toInt() ?? 0;
    final error = status['error'] as String?;
    final c = context.vox;

    if (downloading) {
      return SettingsRow(
        title: widget.title,
        subtitle: 'Downloading, $percent%. Tap to cancel.',
        trailing: SizedBox(
          width: 22,
          height: 22,
          child: CircularProgressIndicator(
            strokeWidth: 2.5,
            value: percent <= 0 ? null : percent / 100,
          ),
        ),
        onTap: () => _call('cancel'),
      );
    }
    if (!installed) {
      return SettingsRow(
        title: widget.title,
        subtitle: error != null
            ? 'Could not download: $error Tap to try again.'
            : '${widget.pitch} Downloads $megabytes MB, so use Wi-Fi.',
        trailing: Text(
          'Download',
          style: Theme.of(context).textTheme.bodyMedium
              ?.copyWith(color: c.accentInk, fontWeight: FontWeight.w600),
        ),
        onTap: _busy ? null : () => _call('download'),
      );
    }
    return SettingsRow(
      title: widget.title,
      subtitle: widget.inUse
          ? 'Installed and in use. Tap to remove it and free $megabytes MB.'
          : 'Installed, not used by your language. Tap to remove it and free '
                '$megabytes MB.',
      onTap: _busy ? null : () => _confirmDelete(megabytes),
    );
  }

  Future<void> _confirmDelete(int megabytes) async {
    final remove = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Remove this speech model?'),
        content: Text(
          widget.inUse
              ? 'Your language uses it, so dictation stops typing until you '
                    'download it again ($megabytes MB).'
              : 'It frees $megabytes MB. You can download it again any time.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Keep'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Remove'),
          ),
        ],
      ),
    );
    if (remove == true) await _call('delete');
  }
}
