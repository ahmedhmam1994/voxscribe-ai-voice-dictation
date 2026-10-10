import 'package:voxscribe_app/features/setup/domain/setup_platform.dart';
import 'package:voxscribe_app/features/setup/domain/setup_status.dart';

/// A phone the test controls: set [status] and read which actions were used.
class FakeSetupPlatform implements SetupPlatform {
  FakeSetupPlatform([this.status = SetupStatus.none]);

  SetupStatus status;
  final calls = <String>[];

  /// Make the next action fail with this message.
  String? failWith;

  @override
  Future<SetupStatus> getStatus() async => status;

  @override
  Future<void> requestMicrophone() => _record('requestMicrophone');

  @override
  Future<void> openAccessibilitySettings() =>
      _record('openAccessibilitySettings');

  @override
  Future<void> openOverlaySettings() => _record('openOverlaySettings');

  @override
  Future<void> setBubbleRunning({required bool running}) async {
    await _record('setBubbleRunning:$running');
    status = status.copyWith(bubbleRunning: running);
  }

  Future<void> _record(String call) async {
    final message = failWith;
    if (message != null) {
      failWith = null;
      throw SetupException(message);
    }
    calls.add(call);
  }
}
