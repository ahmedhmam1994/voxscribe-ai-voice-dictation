/// The text tools the user can set: what the app does to a transcript before
/// it is typed. The lists are plain text, one entry per line, the same format
/// the Windows app uses.
class TextToolsSettings {
  const TextToolsSettings({
    this.voiceCommands = false,
    this.smartFormat = false,
    this.codeDictation = false,
    this.replacements = '',
    this.templates = '',
    this.profiles = '',
    this.sendIt = false,
  });

  /// "period", "new line" and "scratch that" become punctuation and edits.
  final bool voiceCommands;

  /// "send it" presses Enter or Send. Off by default, because it can send a message.
  final bool sendIt;

  /// Spoken emails, web addresses and numbers typed as written. Pro.
  final bool smartFormat;

  /// "camel case user name" becomes userName. Pro.
  final bool codeDictation;

  /// One `heard => replacement` per line.
  final String replacements;

  /// One `name => text with {slots}` per line. Pro.
  final String templates;

  /// One `package => option=value, ...` per line. Pro.
  final String profiles;

  static const defaults = TextToolsSettings();

  TextToolsSettings copyWith({
    bool? voiceCommands,
    bool? smartFormat,
    bool? codeDictation,
    String? replacements,
    String? templates,
    String? profiles,
    bool? sendIt,
  }) {
    return TextToolsSettings(
      voiceCommands: voiceCommands ?? this.voiceCommands,
      smartFormat: smartFormat ?? this.smartFormat,
      codeDictation: codeDictation ?? this.codeDictation,
      replacements: replacements ?? this.replacements,
      templates: templates ?? this.templates,
      profiles: profiles ?? this.profiles,
      sendIt: sendIt ?? this.sendIt,
    );
  }

  @override
  bool operator ==(Object other) =>
      other is TextToolsSettings &&
      other.voiceCommands == voiceCommands &&
      other.smartFormat == smartFormat &&
      other.codeDictation == codeDictation &&
      other.replacements == replacements &&
      other.templates == templates &&
      other.profiles == profiles &&
      other.sendIt == sendIt;

  @override
  int get hashCode => Object.hash(
    voiceCommands,
    smartFormat,
    codeDictation,
    replacements,
    templates,
    profiles,
    sendIt,
  );
}
