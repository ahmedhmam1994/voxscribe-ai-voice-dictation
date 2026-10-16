import 'package:flutter/services.dart';
import 'package:voxscribe_app/features/texttools/domain/text_tools.dart';
import 'package:voxscribe_app/features/texttools/domain/text_tools_repository.dart';

/// Talks to `TextToolsChannel.kt`. If the native side cannot be reached the
/// defaults are used and changes are not saved.
class MethodChannelTextToolsRepository implements TextToolsRepository {
  static const _channel = MethodChannel('com.voxscribe.android/texttools');

  @override
  Future<TextToolsSettings> load() async {
    try {
      final raw = await _channel.invokeMapMethod<String, Object?>(
        'getTextTools',
      );
      if (raw == null) return TextToolsSettings.defaults;
      return TextToolsSettings(
        voiceCommands: raw['voiceCommands'] as bool? ?? false,
        smartFormat: raw['smartFormat'] as bool? ?? false,
        codeDictation: raw['codeDictation'] as bool? ?? false,
        replacements: raw['replacements'] as String? ?? '',
        templates: raw['templates'] as String? ?? '',
        profiles: raw['profiles'] as String? ?? '',
        sendIt: raw['sendIt'] as bool? ?? false,
      );
    } on PlatformException {
      return TextToolsSettings.defaults;
    }
  }

  @override
  Future<void> save(TextToolsSettings settings) async {
    try {
      await _channel.invokeMethod<void>('setTextTools', {
        'voiceCommands': settings.voiceCommands,
        'smartFormat': settings.smartFormat,
        'codeDictation': settings.codeDictation,
        'replacements': settings.replacements,
        'templates': settings.templates,
        'profiles': settings.profiles,
        'sendIt': settings.sendIt,
      });
    } on PlatformException {
      // The screen already shows the new value; it just will not persist.
    }
  }
}
