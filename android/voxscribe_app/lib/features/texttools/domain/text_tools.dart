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
    this.mode = 'default',
    this.autoModes = true,
    this.termPacks = '',
    this.spokenFormats = false,
    this.readBack = false,
    this.formFill = true,
    this.formFillsLeft = 5,
    this.screenSpelling = true,
    this.learnFixes = true,
    this.learned = '',
  });

  /// A word you fix after VoxScribe typed it is spelled your way from then on.
  final bool learnFixes;

  /// The fixes learned so far, one `heard => fixed` per line. Read from the
  /// phone, never saved from here: removing one goes through the repository.
  final String learned;

  /// Names shown on screen while you dictate fix how they are spelled.
  final bool screenSpelling;

  /// The term pack ids switched on, comma separated. None by default.
  final String termPacks;

  /// Doses, legal references and amounts written out for the packs that are on.
  final bool spokenFormats;

  /// The phone reads each dictation from the floating button aloud.
  final bool readBack;

  /// Speak once, fill the whole form: "Name Sam Lee, phone ..., email ..."
  /// puts each part in the box with that label.
  final bool formFill;

  /// Free form fills left before Pro, or -1 with Pro. Read from the phone, never saved.
  final int formFillsLeft;

  /// [termPacks] as a list.
  List<String> get enabledPacks => termPacks
      .split(',')
      .map((id) => id.trim())
      .where((id) => id.isNotEmpty)
      .toList();

  /// The dictation mode: 'default', 'chat', 'email', 'code' (Pro) or 'notes'.
  final String mode;

  /// Pro: the mode switches with the app in front (chat apps use Chat, and so on).
  final bool autoModes;

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
    String? mode,
    bool? autoModes,
    String? termPacks,
    bool? spokenFormats,
    bool? readBack,
    bool? formFill,
    int? formFillsLeft,
    bool? screenSpelling,
    bool? learnFixes,
    String? learned,
  }) {
    return TextToolsSettings(
      voiceCommands: voiceCommands ?? this.voiceCommands,
      smartFormat: smartFormat ?? this.smartFormat,
      codeDictation: codeDictation ?? this.codeDictation,
      replacements: replacements ?? this.replacements,
      templates: templates ?? this.templates,
      profiles: profiles ?? this.profiles,
      sendIt: sendIt ?? this.sendIt,
      mode: mode ?? this.mode,
      autoModes: autoModes ?? this.autoModes,
      termPacks: termPacks ?? this.termPacks,
      spokenFormats: spokenFormats ?? this.spokenFormats,
      readBack: readBack ?? this.readBack,
      formFill: formFill ?? this.formFill,
      formFillsLeft: formFillsLeft ?? this.formFillsLeft,
      screenSpelling: screenSpelling ?? this.screenSpelling,
      learnFixes: learnFixes ?? this.learnFixes,
      learned: learned ?? this.learned,
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
      other.sendIt == sendIt &&
      other.mode == mode &&
      other.autoModes == autoModes &&
      other.termPacks == termPacks &&
      other.spokenFormats == spokenFormats &&
      other.readBack == readBack &&
      other.formFill == formFill &&
      other.formFillsLeft == formFillsLeft &&
      other.screenSpelling == screenSpelling &&
      other.learnFixes == learnFixes &&
      other.learned == learned;

  @override
  int get hashCode => Object.hash(
    voiceCommands,
    smartFormat,
    codeDictation,
    replacements,
    templates,
    profiles,
    sendIt,
    mode,
    autoModes,
    termPacks,
    spokenFormats,
    readBack,
    formFill,
    formFillsLeft,
    screenSpelling,
    learnFixes,
    learned,
  );
}
