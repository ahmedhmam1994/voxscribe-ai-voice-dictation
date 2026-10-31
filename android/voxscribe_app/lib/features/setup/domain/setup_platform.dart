import 'package:voxscribe_app/features/setup/domain/setup_status.dart';

/// Thrown when the phone refuses a setup action.
class SetupException implements Exception {
  const SetupException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// What the setup screen needs from Android. The real implementation talks to
/// native code; tests use a fake.
abstract interface class SetupPlatform {
  Future<SetupStatus> getStatus();

  /// Shows the system permission dialog. The answer shows up in [getStatus].
  Future<void> requestMicrophone();

  Future<void> openAccessibilitySettings();

  Future<void> openOverlaySettings();

  /// Opens this app's notification settings, where they can be allowed.
  Future<void> openNotificationSettings();

  /// Tells the native side the setup screen opened, for its one-time ping.
  Future<void> setupOpened();

  /// Asks Android to add the VoxScribe button tile to Quick Settings.
  Future<QuickTileResult> addQuickTile();

  /// Starts or stops the floating button.
  Future<void> setBubbleRunning({required bool running});
}

/// How a request to add the Quick Settings tile ended.
enum QuickTileResult {
  added,
  alreadyAdded,
  declined,

  /// Android could not ask (older Android, or a phone that ignores the
  /// request), so the user adds the tile by hand.
  manual,
}
