import 'package:flutter/foundation.dart';

/// A word list for a field, built in or imported by the user.
@immutable
class TermPack {
  const TermPack({
    required this.id,
    required this.label,
    required this.count,
    this.user = false,
  });

  /// "medical", "legal", "business", or "user:" and the file's name.
  final String id;
  final String label;

  /// How many terms it holds.
  final int count;

  /// Imported by the user, so it can be removed.
  final bool user;

  @override
  bool operator ==(Object other) =>
      other is TermPack &&
      other.id == id &&
      other.label == label &&
      other.count == count &&
      other.user == user;

  @override
  int get hashCode => Object.hash(id, label, count, user);
}

/// One sentence to read in Teach your voice, and the terms it is about.
@immutable
class TeachLine {
  const TeachLine(this.sentence, this.terms);

  final String sentence;
  final List<String> terms;
}

/// A word that came out differently from what was meant, with how often.
@immutable
class TeachProposal {
  const TeachProposal({
    required this.heard,
    required this.expected,
    this.count = 1,
  });

  final String heard;
  final String expected;
  final int count;
}

/// A pack could not be imported; [message] says why, for the user.
class TermPackException implements Exception {
  const TermPackException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// The term packs and the Teach your voice comparison, which live on the
/// native side so the floating button uses the same lists.
abstract interface class TermPacksPlatform {
  Future<List<TermPack>> list();

  /// Saves [text] as a pack named after [fileName]. Throws [TermPackException].
  Future<TermPack> import(String fileName, String text);

  Future<void> remove(String id);

  /// The sentences to read, for the packs that are on.
  Future<List<TeachLine>> teachScript();

  /// What [heard] got wrong for each line, merged into one list to tick.
  Future<List<TeachProposal>> teachProposals(
    List<(TeachLine line, String heard)> readings,
  );
}
