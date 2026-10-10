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

  /// Starts or stops the floating button.
  Future<void> setBubbleRunning({required bool running});
}
