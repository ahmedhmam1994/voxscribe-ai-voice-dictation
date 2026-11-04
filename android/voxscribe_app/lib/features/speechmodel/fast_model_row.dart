import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/settings/widgets/settings_group.dart';

/// The optional English fast model in Settings: download it once, then switch
/// to it. It decodes faster and is more accurate for English than the bundled
/// Whisper, but it only speaks English, so Whisper stays for Arabic.
///
/// Hides itself when the phone side is not there (tests, older builds).
class FastModelRow extends StatefulWidget {
  const FastModelRow({this.channel, super.key});

  final MethodChannel? channel;

  @override
  State<FastModelRow> createState() => _FastModelRowState();
}

class _FastModelRowState extends State<FastModelRow> {
  late final MethodChannel _channel =
      widget.channel ?? const MethodChannel('com.voxscribe.android/fastmodel');
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
      final raw = await _channel.invokeMapMethod<String, Object?>('status');
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

  Future<void> _call(String method, [Map<String, Object?>? args]) async {
    setState(() => _busy = true);
    try {
      await _channel.invokeMethod<void>(method, args);
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
    final selected = status['selected'] == true;
    final downloading = status['downloading'] == true;
    final percent = (status['percent'] as num?)?.toInt() ?? 0;
    final megabytes = (status['megabytes'] as num?)?.toInt() ?? 131;
    final error = status['error'] as String?;
    final c = context.vox;

    if (downloading) {
      return SettingsRow(
        title: 'English fast model',
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
        title: 'English fast model',
        subtitle: error != null
            ? 'Could not download: $error Tap to try again.'
            : 'Faster and more accurate for English. English only. '
                  'Downloads $megabytes MB, so use Wi-Fi.',
        trailing: Text(
          'Download',
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
            color: c.accentInk,
            fontWeight: FontWeight.w600,
          ),
        ),
        onTap: _busy ? null : () => _call('download'),
      );
    }
    return Column(
      children: [
        SettingsSwitchRow(
          title: 'Use the English fast model',
          subtitle: selected
              ? 'On. English only. Turn off for Arabic or mixed speech.'
              : 'Off. Dictation uses the standard model.',
          value: selected,
          onChanged: (value) {
            if (!_busy) unawaited(_call('select', {'fast': value}));
          },
        ),
        SettingsRow(
          title: 'Remove the English fast model',
          subtitle: 'Frees $megabytes MB. You can download it again.',
          onTap: _busy ? null : () => _call('delete'),
        ),
      ],
    );
  }
}
