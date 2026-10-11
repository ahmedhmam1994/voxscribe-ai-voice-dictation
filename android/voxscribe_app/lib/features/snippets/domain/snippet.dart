/// Say [trigger] on its own and [expansion] is typed in its place.
class Snippet {
  const Snippet({required this.trigger, required this.expansion});

  final String trigger;
  final String expansion;

  /// Triggers match without regard to case or surrounding spaces.
  bool hasSameTrigger(Snippet other) =>
      trigger.trim().toLowerCase() == other.trigger.trim().toLowerCase();
}
