import 'dart:convert';

/// A published Android release on GitHub.
class ReleaseInfo {
  const ReleaseInfo({
    required this.version,
    required this.notes,
    required this.pageUrl,
    this.apkUrl,
  });

  final String version;
  final String notes;
  final String pageUrl;
  final String? apkUrl;

  /// Where the Update button goes: the APK itself when there is one.
  String get downloadUrl => apkUrl ?? pageUrl;
}

/// Android releases share a repository with the Windows app, so they carry
/// their own tag prefix: `android-v1.0.1`.
const androidTagPrefix = 'android-v';

/// '1.2.3', 'v1.2.3' or 'android-v1.2.3' as numbers, ignoring any suffix.
List<int> parseVersion(String text) {
  var cleaned = text.trim().toLowerCase();
  if (cleaned.startsWith(androidTagPrefix)) {
    cleaned = cleaned.substring(androidTagPrefix.length);
  } else if (cleaned.startsWith('v')) {
    cleaned = cleaned.substring(1);
  }
  return cleaned
      .split('.')
      .map((part) => int.tryParse(RegExp(r'^\d+').stringMatch(part) ?? '') ?? 0)
      .toList();
}

/// True when [candidate] is a higher version than [current].
bool isNewerVersion(String candidate, String current) {
  final a = parseVersion(candidate);
  final b = parseVersion(current);
  final length = a.length > b.length ? a.length : b.length;
  for (var i = 0; i < length; i++) {
    final x = i < a.length ? a[i] : 0;
    final y = i < b.length ? b[i] : 0;
    if (x != y) return x > y;
  }
  return false;
}

/// The newest published Android release in GitHub's release list, or null.
ReleaseInfo? parseLatestAndroidRelease(String json) {
  final Object? decoded;
  try {
    decoded = jsonDecode(json);
  } on FormatException {
    return null;
  }
  if (decoded is! List) return null;
  ReleaseInfo? best;
  for (final item in decoded) {
    if (item is! Map<String, Object?>) continue;
    final tag = item['tag_name'];
    if (tag is! String || !tag.startsWith(androidTagPrefix)) continue;
    if (item['draft'] == true || item['prerelease'] == true) continue;
    String? apk;
    final assets = item['assets'];
    if (assets is List) {
      for (final asset in assets) {
        if (asset is! Map<String, Object?>) continue;
        final name = asset['name'];
        final url = asset['browser_download_url'];
        if (name is String && url is String && name.endsWith('.apk')) {
          apk = url;
          break;
        }
      }
    }
    final info = ReleaseInfo(
      version: tag.substring(androidTagPrefix.length),
      notes: (item['body'] as String?)?.trim() ?? '',
      pageUrl: item['html_url'] as String? ?? '',
      apkUrl: apk,
    );
    if (best == null || isNewerVersion(info.version, best.version)) best = info;
  }
  return best;
}

/// What is saved on the phone about releases.
class ReleaseState {
  const ReleaseState({
    required this.version,
    this.lastSeen,
    this.dismissedUpdate,
  });

  final String version;
  final String? lastSeen;
  final String? dismissedUpdate;
}
