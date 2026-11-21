import 'package:voxscribe_app/features/settings/domain/app_settings.dart';
import 'package:voxscribe_app/features/settings/domain/settings_repository.dart';

/// Settings kept in memory. [saved] always holds what was last stored.
class FakeSettingsRepository implements SettingsRepository {
  FakeSettingsRepository([this.saved = AppSettings.defaults]);

  AppSettings saved;

  bool leaverDue = false;
  bool leaverAnswered = false;
  String? leaverReason;

  @override
  Future<AppSettings> load() async => saved;

  @override
  Future<void> setCleanup({required bool value}) async {
    saved = saved.copyWith(cleanup: value);
  }

  @override
  Future<void> setTrailingSpace({required bool value}) async {
    saved = saved.copyWith(trailingSpace: value);
  }

  @override
  Future<void> setUsagePing({required bool value}) async {
    saved = saved.copyWith(usagePing: value);
  }

  @override
  Future<void> setRecordingMode(RecordingMode value) async {
    saved = saved.copyWith(recordingMode: value);
  }

  @override
  Future<void> setBubbleSize(BubbleSize value) async {
    saved = saved.copyWith(bubbleSize: value);
  }

  @override
  Future<void> setTheme(ThemeChoice value) async {
    saved = saved.copyWith(theme: value);
  }

  @override
  Future<void> setHandsFree({required bool value}) async {
    saved = saved.copyWith(handsFree: value);
  }

  @override
  Future<bool> leaverQuestionDue() async => leaverDue && !leaverAnswered;

  @override
  Future<void> answerLeaverQuestion(String? reason) async {
    leaverAnswered = true;
    leaverReason = reason;
  }
}
