/// The server's answer when a license key is unlocked on this phone.
class ActivationResult {
  const ActivationResult({required this.ok, required this.message});

  final bool ok;

  /// A short reason shown to the user when [ok] is false.
  final String message;
}

/// Where the Pro license lives. The same key unlocks Windows and this phone.
abstract interface class ProRepository {
  Future<bool> isPro();

  /// Checks the key, claims it for this phone and, if accepted, keeps it.
  Future<ActivationResult> activate(String key);

  Future<void> deactivate();

  Future<void> openPurchasePage();
}
