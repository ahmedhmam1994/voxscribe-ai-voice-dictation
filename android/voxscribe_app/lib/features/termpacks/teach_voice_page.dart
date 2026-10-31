import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/features/dictation/domain/dictation_engine.dart';
import 'package:voxscribe_app/features/termpacks/domain/term_packs.dart';
import 'package:voxscribe_app/features/texttools/domain/corrections.dart';
import 'package:voxscribe_app/features/texttools/text_tools_controller.dart';
import 'package:voxscribe_app/shared/widgets/vox_card.dart';

/// Teach VoxScribe your voice: read a short script, see the words that came
/// out wrong, and tick the ones to fix from then on. The fixes become word
/// replacements, so they apply everywhere you dictate.
class TeachVoicePage extends StatefulWidget {
  const TeachVoicePage({
    required this.engine,
    required this.platform,
    required this.textTools,
    super.key,
  });

  final DictationEngine engine;
  final TermPacksPlatform platform;
  final TextToolsController textTools;

  @override
  State<TeachVoicePage> createState() => _TeachVoicePageState();
}

enum _Step { idle, recording, listening }

class _TeachVoicePageState extends State<TeachVoicePage> {
  List<TeachLine>? _script;
  var _index = 0;
  var _step = _Step.idle;

  /// What was heard for each line read so far.
  final _heard = <int, String>{};
  List<TeachProposal> _misheard = const [];
  String? _message;

  /// Set once the reading is over.
  List<TeachProposal>? _results;
  final _ticked = <int>{};

  @override
  void initState() {
    super.initState();
    widget.platform.teachScript().then((script) {
      if (mounted) setState(() => _script = script);
    });
  }

  @override
  Widget build(BuildContext context) {
    final script = _script;
    final results = _results;
    return Scaffold(
      appBar: AppBar(title: const Text('Teach your voice')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
        children: [
          if (script == null)
            const Center(child: CircularProgressIndicator())
          else if (script.isEmpty)
            const Text('No sentences to read on this phone.')
          else if (results == null)
            ..._reading(context, script)
          else
            ..._resultsView(context, results),
        ],
      ),
    );
  }

  List<Widget> _reading(BuildContext context, List<TeachLine> script) {
    final c = context.vox;
    final theme = Theme.of(context).textTheme;
    final line = script[_index];
    final heard = _heard[_index];
    final last = _index == script.length - 1;
    return [
      Text(
        'Read each sentence out loud at your normal pace. VoxScribe listens '
        'with the speech model it uses now, then shows the words it misheard '
        'in your voice. About three minutes. Recordings are not saved.',
        style: theme.bodyMedium,
      ),
      const SizedBox(height: 16),
      Text(
        'Sentence ${_index + 1} of ${script.length}',
        style: theme.labelLarge?.copyWith(color: c.muted),
      ),
      const SizedBox(height: 8),
      VoxCard(
        child: Text(
          '“${line.sentence}”',
          style: theme.titleMedium?.copyWith(height: 1.4),
        ),
      ),
      const SizedBox(height: 14),
      SizedBox(
        height: 52,
        child: FilledButton.icon(
          onPressed: _step == _Step.listening ? null : _toggle,
          style: FilledButton.styleFrom(
            backgroundColor: _step == _Step.recording ? c.red : c.accent,
            foregroundColor: _step == _Step.recording
                ? Colors.white
                : c.onAccent,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(14),
            ),
          ),
          icon: Icon(
            _step == _Step.recording ? Icons.stop_rounded : Icons.mic_none,
          ),
          label: Text(switch (_step) {
            _Step.recording => 'Stop',
            _Step.listening => 'Listening...',
            _Step.idle => heard == null ? 'Start recording' : 'Record again',
          }),
        ),
      ),
      if (_message case final message?) ...[
        const SizedBox(height: 10),
        Text(message, style: theme.bodyMedium?.copyWith(color: c.muted)),
      ],
      if (heard != null) ...[
        const SizedBox(height: 12),
        Text('Heard: “$heard”', style: theme.bodyMedium),
        const SizedBox(height: 4),
        Text(
          _misheard.isEmpty
              ? 'All the key words were right.'
              : 'Misheard: ${_misheard.map((p) => '“${p.heard}” (meant ${p.expected})').join(', ')}',
          style: theme.bodyMedium?.copyWith(
            color: _misheard.isEmpty ? c.accentInk : c.text,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
      const SizedBox(height: 18),
      Row(
        children: [
          TextButton(
            onPressed: _step == _Step.idle ? () => _next(script) : null,
            child: Text('Skip this one', style: TextStyle(color: c.muted)),
          ),
          const Spacer(),
          OutlinedButton(
            onPressed: _step == _Step.idle && heard != null
                ? () => _next(script)
                : null,
            child: Text(last ? 'See results' : 'Next sentence'),
          ),
        ],
      ),
    ];
  }

  List<Widget> _resultsView(BuildContext context, List<TeachProposal> results) {
    final theme = Theme.of(context).textTheme;
    final c = context.vox;
    final read = _heard.length;
    if (read == 0) {
      return [
        Text(
          'No sentences were recorded, so there is nothing to learn yet.',
          style: theme.bodyMedium,
        ),
      ];
    }
    if (results.isEmpty) {
      return [
        Text(
          'VoxScribe understood all the key words in $read '
          'sentence${read == 1 ? '' : 's'}. Nothing to fix.',
          style: theme.bodyLarge,
        ),
      ];
    }
    return [
      Text(
        'These words came out differently from what you meant. Tick the ones '
        'to fix from now on. A fix changes that word everywhere you dictate, '
        'so untick any that is a real word you also use.',
        style: theme.bodyMedium,
      ),
      const SizedBox(height: 12),
      // A Material, not a VoxCard, so the ticks show their ink.
      Material(
        color: c.card,
        clipBehavior: Clip.antiAlias,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: BorderSide(color: c.border),
        ),
        child: Column(
          children: [
            for (var i = 0; i < results.length; i++)
              CheckboxListTile(
                contentPadding: const EdgeInsets.symmetric(horizontal: 16),
                value: _ticked.contains(i),
                onChanged: (on) => setState(
                  () => on == true ? _ticked.add(i) : _ticked.remove(i),
                ),
                title: Text('“${results[i].heard}”  →  ${results[i].expected}'),
                subtitle: results[i].count > 1
                    ? Text(
                        'Heard ${results[i].count} times',
                        style: theme.bodySmall?.copyWith(color: c.muted),
                      )
                    : null,
              ),
          ],
        ),
      ),
      const SizedBox(height: 16),
      SizedBox(
        height: 52,
        child: FilledButton(
          onPressed: _ticked.isEmpty ? null : () => _addTicked(results),
          style: FilledButton.styleFrom(
            backgroundColor: c.accent,
            foregroundColor: c.onAccent,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(14),
            ),
          ),
          child: const Text('Add to my word replacements'),
        ),
      ),
    ];
  }

  Future<void> _toggle() async {
    if (_step == _Step.recording) {
      setState(() => _step = _Step.listening);
      try {
        final result = await widget.engine.stop();
        await _onHeard(result.text.trim());
      } on DictationException catch (e) {
        if (mounted) {
          setState(() {
            _step = _Step.idle;
            _message = 'Could not transcribe: ${e.message}';
          });
        }
      }
      return;
    }
    try {
      await widget.engine.start();
      if (mounted) {
        setState(() {
          _step = _Step.recording;
          _message = 'Recording...';
        });
      }
    } on DictationException catch (e) {
      if (mounted) setState(() => _message = e.message);
    }
  }

  Future<void> _onHeard(String heard) async {
    if (!mounted) return;
    if (heard.isEmpty) {
      setState(() {
        _step = _Step.idle;
        _message =
            'VoxScribe heard nothing. Try again, a little closer to the mic.';
      });
      return;
    }
    final line = _script![_index];
    final misheard = await widget.platform.teachProposals([(line, heard)]);
    if (!mounted) return;
    setState(() {
      _heard[_index] = heard;
      _misheard = misheard;
      _step = _Step.idle;
      _message = null;
    });
  }

  Future<void> _next(List<TeachLine> script) async {
    if (_index < script.length - 1) {
      setState(() {
        _index++;
        _misheard = const [];
        _message = null;
      });
      return;
    }
    final readings = [
      for (final entry in _heard.entries) (script[entry.key], entry.value),
    ];
    final results = readings.isEmpty
        ? const <TeachProposal>[]
        : await widget.platform.teachProposals(readings);
    if (!mounted) return;
    setState(() {
      _results = results;
      _ticked
        ..clear()
        ..addAll(List.generate(results.length, (i) => i));
    });
  }

  Future<void> _addTicked(List<TeachProposal> results) async {
    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);
    var added = 0;
    for (final i in _ticked.toList()..sort()) {
      final status = await widget.textTools.addCorrection(
        results[i].heard,
        results[i].expected,
      );
      if (status == CorrectionStatus.added ||
          status == CorrectionStatus.updated) {
        added++;
      }
    }
    messenger.showSnackBar(
      SnackBar(
        content: Text(
          added == 0
              ? 'Those fixes were already in your word replacements.'
              : 'Added $added word fix${added == 1 ? '' : 'es'}.',
        ),
      ),
    );
    navigator.pop();
  }

  @override
  void dispose() {
    if (_step == _Step.recording) widget.engine.stop().ignore();
    super.dispose();
  }
}
