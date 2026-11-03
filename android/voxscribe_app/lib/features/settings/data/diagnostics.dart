import 'package:flutter/services.dart';

/// A short plain-text report for a stuck user to paste into a message: the
/// last first-run step reached, the app and Android versions, the phone.
/// Built on the phone by `FirstRun.diagnosticsText`; nothing is sent anywhere.
Future<String> loadDiagnostics() async {
  try {
    const channel = MethodChannel('com.voxscribe.android/settings');
    return await channel.invokeMethod<String>('getDiagnostics') ?? '';
  } on PlatformException {
    return '';
  } on MissingPluginException {
    return '';
  }
}
