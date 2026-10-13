/// What each version added. A version with no entry here shows no "what's
/// new" sheet on first launch, so a quiet bug fix stays quiet.
const whatsNewByVersion = <String, List<String>>{
  '1.0.0': [
    'Voice commands: say "period", "new line" or "question mark" and get the symbol.',
    'Say "scratch that" to take back what you just dictated, or "delete last word".',
    'Word replacements, smart formatting and code dictation, switched on in Text tools.',
    'Fill-in templates and per-app profiles, so each app can dictate its own way.',
    'A new animated intro when the app opens.',
  ],
};

List<String>? whatsNewFor(String version) => whatsNewByVersion[version];
