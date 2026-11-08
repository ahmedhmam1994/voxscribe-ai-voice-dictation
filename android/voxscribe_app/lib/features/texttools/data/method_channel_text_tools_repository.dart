import 'package:flutter/services.dart';
import 'package:voxscribe_app/features/texttools/domain/text_tools.dart';
import 'package:voxscribe_app/features/texttools/domain/text_tools_repository.dart';
import 'package:voxscribe_app/features/texttools/domain/word_lists.dart';

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
        mode: raw['mode'] as String? ?? 'default',
        autoModes: raw['autoModes'] as bool? ?? true,
        termPacks: raw['termPacks'] as String? ?? '',
        spokenFormats: raw['spokenFormats'] as bool? ?? false,
        readBack: raw['readBack'] as bool? ?? false,
        formFill: raw['formFill'] as bool? ?? true,
        formFillsLeft: raw['formFillsLeft'] as int? ?? 5,
        screenSpelling: raw['screenSpelling'] as bool? ?? true,
        learnFixes: raw['learnFixes'] as bool? ?? true,
        learned: raw['learned'] as String? ?? '',
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
        'mode': settings.mode,
        'autoModes': settings.autoModes,
        'termPacks': settings.termPacks,
        'spokenFormats': settings.spokenFormats,
        'readBack': settings.readBack,
        'formFill': settings.formFill,
        'screenSpelling': settings.screenSpelling,
        'learnFixes': settings.learnFixes,
      });
    } on PlatformException {
      // The screen already shows the new value; it just will not persist.
    }
  }

  @override
  Future<String> addLearned(List<ReplacementRule> fixes) async {
    try {
      return await _channel.invokeMethod<String>('addLearned', {
            'lines': fixes
                .map((f) => '${f.heard} => ${f.replacement}')
                .join('\n'),
          }) ??
          '';
    } on PlatformException {
      return '';
    }
  }

  @override
  Future<String> forgetLearned(String heard) async {
    try {
      return await _channel.invokeMethod<String>('forgetLearned', {
            'heard': heard,
          }) ??
          '';
    } on PlatformException {
      return '';
    }
  }
}
