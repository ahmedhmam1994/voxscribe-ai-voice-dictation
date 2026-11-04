/// What each version added. A version with no entry here shows no "what's
/// new" sheet on first launch, so a quiet bug fix stays quiet.
const whatsNewByVersion = <String, List<String>>{
  '1.1.4': [
    'Dictating into a draft no longer erases it: your words are added at the cursor and the text you already wrote stays.',
    'Share a voice note to VoxScribe: in WhatsApp or any app, share an audio file to VoxScribe and the text comes back.',
    'English fast model: an optional download in Settings that types English several times faster and more accurately. The standard model stays for Arabic and mixed speech.',
    'Learns your words: fix a word VoxScribe got wrong and it makes that fix for you from then on.',
    'Fill forms by voice: say "Name Sam Lee, phone 555 0100" and every box on the form fills at once.',
    'Names shown on screen, like the person you are writing to, are spelled right.',
    'Smart formatting reads "three forty five pm" as 3:45 PM and "order number four eight two nine" as 4829.',
    'A privacy receipt in Settings lists every time VoxScribe went online and what it sent. Never your words.',
  ],
  '1.1.3': [
    'Term packs: medical, law and business word lists fix how field words are written, like "metformin" or "MRI". Add your own list too. Find them under Settings, Words for your field.',
    'Teach your voice: read a few sentences aloud and VoxScribe finds the words it hears wrong, then adds the fixes for you.',
    'Spoken formats for the packs: "one twenty over eighty" becomes 120/80, "five milligrams twice daily" becomes 5 mg BID.',
    'Read it back: the floating button can read your dictation aloud with the offline voice on your phone, and the Dictation screen has a Listen button.',
    'A Quick Settings tile turns the floating button on and off from the notification shade.',
    'A reminder on the Dictation screen until setup is finished.',
    'Livelier screens: a live wave while you talk, words that type themselves in, and a smoother Insights page.',
  ],
  '1.1.2': [
    'A new Floating button group in Settings: record by holding, by tapping once to start and once to stop, or both.',
    'Choose a small, medium or large floating button.',
    'After your first dictation, a one time tip tells you about tapping to start and stop.',
    'Two more anonymous usage pings, the first time you dictate and once on each day you dictate: versions and a random id, never audio or text. Turn them off with the usage ping switch in Settings.',
  ],
  '1.1.1': [
    'Transcribe audio and video files: tap the file icon on the Dictation screen, then save the text or .srt captions. A whole folder at once is Pro, with 2 free tries.',
    'Dictation modes: Chat, Email, Code and Notes tidy your words to fit what you write. With Pro, the mode switches by itself with the app.',
    'One Pro key now covers two PCs and two phones, and removing the license frees this phone for another one.',
    'The button shows a live mic level while you talk, so you can see it hears you.',
    'A small wave while your words are turned into text.',
    'A check mark when the text is typed, and a short shake when it could not be.',
    'The button fades in and out with the keyboard and sinks a little when you press it.',
    'A ring fills in during the last 15 seconds before the 2 minute recording limit.',
    'While you drag the button, a label at the bottom shows where to drop it to hide it.',
    'Insights numbers count up and the week chart grows in. New dictations fade into Today.',
    'The setup screen shows a short animation of how dictating works.',
    'Your history, word lists and Pro key are no longer copied to cloud backups or a new phone.',
  ],
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
