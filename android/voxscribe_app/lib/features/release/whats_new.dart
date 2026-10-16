/// What each version added. A version with no entry here shows no "what's
/// new" sheet on first launch, so a quiet bug fix stays quiet.
const whatsNewByVersion = <String, List<String>>{
  '1.1.0': [
    'Tap the button to start and stop, or hold it as before. Drag it to the bottom to hide it for 10 minutes.',
    'The button stays out of password and PIN boxes.',
    'Say "capitalize that", "all caps" or "replace X with Y" to change what you just said.',
    'Say "send it" to tap the app\'s Send button. Turn it on in Settings.',
    'Settings has a page for each text tool, with every voice command listed.',
    'Fix a word that was heard wrong, right from the Dictation screen.',
    'Email, web address and number boxes get the text the way they expect.',
    'Export and import your word replacements as a file.',
    'A once a day anonymous usage ping (versions and a random id, never audio or text). Turn it off in Settings.',
  ],
  '1.0.0': [
    'Voice commands: say "period", "new line" or "question mark" and get the symbol.',
    'Say "scratch that" to take back what you just dictated, or "delete last word".',
    'Word replacements, smart formatting and code dictation, switched on in Text tools.',
    'Fill-in templates and per-app profiles, so each app can dictate its own way.',
    'A new animated intro when the app opens.',
  ],
};

List<String>? whatsNewFor(String version) => whatsNewByVersion[version];
