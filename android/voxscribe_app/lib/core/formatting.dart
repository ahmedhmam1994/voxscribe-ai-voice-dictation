/// Clock text such as "9:48 AM".
String formatClock(DateTime time) {
  final hour = time.hour % 12 == 0 ? 12 : time.hour % 12;
  final minute = time.minute.toString().padLeft(2, '0');
  final suffix = time.hour < 12 ? 'AM' : 'PM';
  return '$hour:$minute $suffix';
}

/// Seconds with one decimal, such as "2.4 s".
String formatSeconds(Duration duration) {
  return '${(duration.inMilliseconds / 1000).toStringAsFixed(1)} s';
}

/// "1 word" or "12 words".
String formatWordCount(int count) => count == 1 ? '1 word' : '$count words';
