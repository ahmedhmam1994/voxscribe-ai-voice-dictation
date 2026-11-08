import 'dart:convert';

import 'package:voxscribe_app/features/snippets/domain/snippet.dart';

/// The word lists file shared with the Windows app (`core/word_lists.py`):
///
/// ```json
/// {
///   "format": "voxscribe-word-lists",
///   "version": 2,
///   "vocabulary": ["VoxScribe"],
///   "replacements": [{"heard": "vox scribe", "replacement": "VoxScribe"}],
///   "learned": [{"heard": "shivon", "fixed": "Siobhan"}],
///   "snippets": [{"trigger": "my sig", "expansion": "Best, Sam"}],
///   "templates": [{"name": "bug report", "body": "Title: {title}"}],
///   "profile": {"field": "medical", "app": "email"}
/// }
/// ```
///
/// Version 1 files have only the vocabulary and replacements; every later key
/// is optional. The vocabulary and the voice profile are Windows features, so
/// an import counts the vocabulary and leaves both out. A plain text file with
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

/// The file contents. [templatesText] and [learnedText] are the settings
/// box forms (`name => body` with `\n` for a line break, `heard => fixed`).
String buildWordListsFile(
  String replacementsText, {
  String templatesText = '',
  String learnedText = '',
  List<Snippet> snippets = const [],
}) {
  final data = {
    'format': wordListsFormat,
    'version': 2,
    'vocabulary': <String>[],
    'replacements': [
      for (final rule in parseReplacementsText(replacementsText))
        {'heard': rule.heard, 'replacement': rule.replacement},
    ],
    'learned': [
      for (final rule in parseReplacementsText(learnedText))
        if (rule.replacement.isNotEmpty)
          {'heard': rule.heard, 'fixed': rule.replacement},
    ],
    'snippets': [
      for (final snippet in snippets)
        if (snippet.trigger.trim().isNotEmpty && snippet.expansion.isNotEmpty)
          {'trigger': snippet.trigger.trim(), 'expansion': snippet.expansion},
    ],
    'templates': [
      for (final rule in parseReplacementsText(templatesText))
        if (rule.replacement.isNotEmpty)
          {
            'name': rule.heard,
            'body': rule.replacement.replaceAll(r'\n', '\n'),
          },
    ],
  };
  return '${const JsonEncoder.withIndent('  ').convert(data)}\n';
}

/// Templates as settings box lines: a line break in a body becomes `\n`.
List<ReplacementRule> templateLines(List<ReplacementRule> templates) => [
  for (final t in templates)
    ReplacementRule(t.heard, t.replacement.replaceAll('\n', r'\n')),
];

List<(String, String)> _pairsIn(
  Map<dynamic, dynamic> data,
  String key,
  String first,
  String second, {
  bool trimSecond = true,
}) {
  final found = <(String, String)>[];
  final listed = data[key];
  if (listed is! List) return found;
  for (final item in listed) {
    if (item is! Map) continue;
    final a = item[first];
    final b = item[second];
    if (a is String &&
        a.trim().isNotEmpty &&
        b is String &&
        b.trim().isNotEmpty) {
      found.add((a.trim(), trimSecond ? b.trim() : b));
    }
  }
  return found;
}

/// What a word lists file holds.
class WordListImport {
  const WordListImport(
    this.rules, {
    this.vocabularyCount = 0,
    this.learned = const [],
    this.snippets = const [],
    this.templates = const [],
  });

  final List<ReplacementRule> rules;

  /// Fixes learned on the other device: what was heard and what it should be.
  final List<ReplacementRule> learned;

  final List<Snippet> snippets;

  /// Template names and bodies, with real line breaks in the bodies.
  final List<ReplacementRule> templates;

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
    return WordListImport(
      rules,
      vocabularyCount: count,
      learned: [
        for (final (heard, fixed) in _pairsIn(
          data,
          'learned',
          'heard',
          'fixed',
        ))
          ReplacementRule(heard, fixed),
      ],
      snippets: [
        for (final (trigger, expansion) in _pairsIn(
          data,
          'snippets',
          'trigger',
          'expansion',
          trimSecond: false,
        ))
          Snippet(trigger: trigger, expansion: expansion),
      ],
      templates: [
        for (final (name, body) in _pairsIn(
          data,
          'templates',
          'name',
          'body',
          trimSecond: false,
        ))
          ReplacementRule(name, body),
      ],
    );
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
