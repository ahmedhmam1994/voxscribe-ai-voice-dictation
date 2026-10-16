/// What happened when a correction was offered to the word replacements.
enum CorrectionStatus { added, updated, unchanged, invalid }

/// The new replacements text and what changed in it.
class CorrectionResult {
  const CorrectionResult(this.text, this.status);

  final String text;
  final CorrectionStatus status;
}

final _edgeJunk = RegExp(r'^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$', unicode: true);

/// The words picked from a transcript, without the punctuation and spaces
/// around them. "whisker," becomes "whisker"; apostrophes and hyphens inside a
/// word stay.
String cleanHeard(String selection) {
  final collapsed = selection.trim().replaceAll(RegExp(r'\s+'), ' ');
  return collapsed.replaceAll(_edgeJunk, '');
}

/// Every word of [text], as it was written, for the user to pick from.
List<String> wordsOf(String text) {
  return text
      .split(RegExp(r'\s+'))
      .where((word) => cleanHeard(word).isNotEmpty)
      .toList();
}

/// Adds `heard => replacement` to [existing], the replacements text with one
/// rule per line. A rule for the same heard words (any case) is updated in
/// place, so correcting a correction does not leave two rules fighting. Other
/// lines are left exactly as they were.
CorrectionResult applyCorrection(
  String existing,
  String heard,
  String replacement,
) {
  final cleanedHeard = cleanHeard(heard);
  final cleanedReplacement = replacement.trim().replaceAll(
    RegExp(r'\s*\n\s*'),
    ' ',
  );
  if (cleanedHeard.isEmpty ||
      cleanedReplacement.isEmpty ||
      cleanedHeard == cleanedReplacement) {
    return CorrectionResult(existing, CorrectionStatus.invalid);
  }

  final lines = existing.isEmpty ? <String>[] : existing.split('\n');
  for (var i = 0; i < lines.length; i++) {
    final at = lines[i].indexOf('=>');
    if (at < 0) continue;
    final sameHeard =
        lines[i].substring(0, at).trim().toLowerCase() ==
        cleanedHeard.toLowerCase();
    if (!sameHeard) continue;
    if (lines[i].substring(at + 2).trim() == cleanedReplacement) {
      return CorrectionResult(existing, CorrectionStatus.unchanged);
    }
    lines[i] = '$cleanedHeard => $cleanedReplacement';
    return CorrectionResult(lines.join('\n'), CorrectionStatus.updated);
  }

  final base = existing.trimRight();
  final rule = '$cleanedHeard => $cleanedReplacement';
  return CorrectionResult(
    base.isEmpty ? rule : '$base\n$rule',
    CorrectionStatus.added,
  );
}
