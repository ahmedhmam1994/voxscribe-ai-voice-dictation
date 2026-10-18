import 'package:flutter/foundation.dart';
import 'package:voxscribe_app/features/pro/domain/pro_repository.dart';

/// Whether Pro is unlocked, and the steps to unlock or remove it.
class ProController extends ChangeNotifier {
  ProController({required this.repository});

  final ProRepository repository;

  var _isPro = false;
  var _busy = false;
  String? _errorMessage;

  bool get isPro => _isPro;

  /// True while a key is being checked with the server.
  bool get busy => _busy;

  /// Why the last unlock failed, or null.
  String? get errorMessage => _errorMessage;

  /// What happened to the license after it was removed, or null.
  String? get notice => _notice;
  String? _notice;

  Future<void> load() async {
    _isPro = await repository.isPro();
    notifyListeners();
  }

  Future<void> activate(String key) async {
    if (_busy) return;
    if (key.trim().isEmpty) {
      _errorMessage = 'Paste your license key first.';
      notifyListeners();
      return;
    }
    _busy = true;
    _errorMessage = null;
    _notice = null;
    notifyListeners();

    final result = await repository.activate(key);
    _busy = false;
    if (result.ok) {
      _isPro = true;
    } else {
      _errorMessage = result.message;
    }
    notifyListeners();
  }

  Future<void> deactivate() async {
    if (_busy) return;
    _busy = true;
    notifyListeners();
    final result = await repository.deactivate();
    _busy = false;
    _errorMessage = null;
    _notice = result.ok
        ? 'License removed. The key is free to use on another phone.'
        : 'License removed from this phone, but the server could not be '
              'reached, so this phone may still count as one of the key\'s two. '
              'Unlock and remove it again when online to free it.';
    await load();
  }

  Future<void> openPurchasePage() => repository.openPurchasePage();
}
