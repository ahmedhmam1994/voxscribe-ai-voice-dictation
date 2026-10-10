/// Where the dictation flow is right now.
enum DictationStatus {
  ready,
  recording,
  transcribing,

  /// The last recording contained no recognizable speech.
  noSpeech,
  failed,
}
