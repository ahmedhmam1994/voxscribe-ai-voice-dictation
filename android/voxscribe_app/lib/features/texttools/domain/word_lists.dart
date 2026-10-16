import 'dart:convert';

/// The word lists file shared with the Windows app (`core/word_lists.py`):
///
/// ```json
/// {
///   "format": "voxscribe-word-lists",
///   "version": 1,
///   "vocabulary": ["VoxScribe"],
///   "replacements": [{"heard": "vox scribe", "replacement": "VoxScribe"}]
/// }
/// ```
///
/// The phone only uses the replacements; the vocabulary is a Windows feature,
/// so an import counts those terms and leaves them out. A plain text file with
/// one `heard => replacement` per line imports too.
const wordListsFormat = 'voxscribe-word-lists';
const wordListsFileName = 'voxscribe-word-lists.json';

class ReplacementRule {
  const ReplacementRule(this.heard, this.replacement);

  final String heard;
  final String replacement;

  @override
  bool operator ==(Object other) =>
      other is ReplacementRule &&
      other.heard == heard &&
      other.replacement == replacement;

  @override
  int get hashCode => Object.hash(heard, replacement);

  @override
  String toString() => '$heard => $replacement';
}

/// The rules in the replacements box: lines with `=>` and words on the left.
List<ReplacementRule> parseReplacementsText(String text) {
  final rules = <ReplacementRule>[];
  for (final line in const LineSplitter().convert(text)) {
    final at = line.indexOf('=>');
    if (at < 0) continue;
    final heard = line.substring(0, at).trim();
    if (heard.isEmpty) continue;
    rules.add(ReplacementRule(heard, line.substring(at + 2).trim()));
  }
  return rules;
}

/// The file contents for the replacements text.
String buildWordListsFile(String replacementsText) {
  final data = {
    'format': wordListsFormat,
    'version': 1,
    'vocabulary': <String>[],
    'replacements': [
      for (final rule in parseReplacementsText(replacementsText))
        {'heard': rule.heard, 'replacement': rule.replacement},
    ],
  };
  return '${const JsonEncoder.withIndent('  ').convert(data)}\n';
}

/// What a word lists file holds.
class WordListImport {
  const WordListImport(this.rules, {this.vocabularyCount = 0});

  final List<ReplacementRule> rules;

  /// Vocabulary terms in the file, which the phone does not use.
  final int vocabularyCount;
}

/// Reads an exported file or a plain text list. Throws a [FormatException]
/// with a message for the user when the file holds neither.
WordListImport parseWordListImport(String text) {
  var body = text.trim();
  if (body.startsWith('﻿')) body = body.substring(1).trim();
  if (body.startsWith('{')) {
    const notOurs = FormatException('This file is not a VoxScribe word list.');
    final Object? data;
    try {
      data = jsonDecode(body);
    } on FormatException {
      throw notOurs;
    }
    if (data is! Map || data['format'] != wordListsFormat) throw notOurs;
    final vocabulary = data['vocabulary'];
    final count = vocabulary is List
        ? vocabulary
              .whereType<String>()
              .where((t) => t.trim().isNotEmpty)
              .length
        : 0;
    final rules = <ReplacementRule>[];
    final listed = data['replacements'];
    if (listed is List) {
      for (final rule in listed) {
        if (rule is! Map) continue;
        final heard = rule['heard'];
        final replacement = rule['replacement'] ?? '';
        if (heard is String &&
            heard.trim().isNotEmpty &&
            replacement is String) {
          rules.add(ReplacementRule(heard.trim(), replacement.trim()));
        }
      }
    }
    return WordListImport(rules, vocabularyCount: count);
  }
  final rules = parseReplacementsText(body);
  if (rules.isEmpty) {
    throw const FormatException(
      'No word list found. Expected a VoxScribe export or '
      '"heard => replacement" lines.',
    );
  }
  return WordListImport(rules);
}

/// The new replacements text after an import, and how many rules it added
/// and changed.
class ReplacementsMerge {
  const ReplacementsMerge(
    this.text, {
    required this.added,
    required this.changed,
  });

  final String text;
  final int added;
  final int changed;
}

/// Adds [incoming] to the replacements [existing] text. A rule for the same
/// heard words (any case) is rewritten in place, so two rules never fight;
/// new rules go at the end. Every other line stays exactly as it was.
ReplacementsMerge mergeReplacements(
  String existing,
  List<ReplacementRule> incoming,
) {
  final lines = existing.trimRight().isEmpty
      ? <String>[]
      : const LineSplitter().convert(existing.trimRight());
  final lineOf = <String, int>{};
  for (var i = 0; i < lines.length; i++) {
    final at = lines[i].indexOf('=>');
    if (at < 0) continue;
    final heard = lines[i].substring(0, at).trim();
    if (heard.isNotEmpty) lineOf.putIfAbsent(heard.toLowerCase(), () => i);
  }
  var added = 0;
  var changed = 0;
  for (final rule in incoming) {
    final key = rule.heard.toLowerCase();
    final line = rule.replacement.isEmpty
        ? '${rule.heard} =>'
        : '${rule.heard} => ${rule.replacement}';
    final at = lineOf[key];
    if (at == null) {
      lineOf[key] = lines.length;
      lines.add(line);
      added++;
      continue;
    }
    final old = lines[at];
    final oldReplacement = old.substring(old.indexOf('=>') + 2).trim();
    if (oldReplacement != rule.replacement) changed++;
    if (old.trim() != line) lines[at] = line;
  }
  return ReplacementsMerge(lines.join('\n'), added: added, changed: changed);
}
