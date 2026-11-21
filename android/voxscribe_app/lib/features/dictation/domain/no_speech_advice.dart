/// What to tell the user when a dictation in the app came back with no
/// words, from the reason the engine gave. The in-app button is held while
/// talking, so a too-short press means letting go too soon.
String noSpeechAdvice(String? reason) => switch (reason) {
  'too_short' => 'Too short to hear. Hold the button the whole time you talk.',
  'silent' =>
    'The microphone heard nothing. Check it is not muted or being used by '
        'a call or another app.',
  'quiet' => 'Very quiet. Hold the phone closer, or speak a little louder.',
  'unclear' =>
    'Heard sound but no words. Try again a little slower, closer to the '
        'phone.',
  _ => 'Nothing was heard. Check the microphone is not muted.',
};
