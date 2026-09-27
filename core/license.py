"""Offline Pro-license verification, plus a one-time online activation check.

VoxScribe stays free forever for its core dictation features -- this only
gates the Pro tier (snippets/macros, see core/snippets.py, and future Pro
features). Day-to-day verification (is_pro(), called on every launch and
Settings open) works fully offline, with nothing phoning home: a license
key is a signed blob, verified locally against a public key embedded in
this file. Signing itself happens outside this app entirely, with a
private key that never ships (see scripts/generate_license_key.py and
.gitignore's note on license_signing_key.raw) -- this module can only
verify keys, never mint them.

Key format: base32(license_id[8 bytes] || Ed25519 signature[64 bytes]),
grouped into dash-separated blocks for readability. There's no expiry
baked into the key itself -- a valid key is a perpetual unlock, matching
a one-time-purchase Pro tier rather than a subscription.

**activate_online()** is the one deliberate exception to "fully offline":
without it, a valid key string can be typed into any number of machines
with zero enforcement, since local-only verification has no way to know
a key was already used elsewhere. It's called once, when the user clicks
Unlock in Settings, and checks/claims the key against a small server-side
registry (see docs/api/activate.js) keyed by a hardware id rather than
personal information. Once a key has been accepted this way, ongoing use
(is_pro()) goes back to the fully offline signature check -- no repeated
network calls, no telemetry beyond this one activation request. Disclosed
in docs/privacy.html.
"""

from __future__ import annotations

import base64
import json
import subprocess
import urllib.error
import urllib.request

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from PySide6.QtCore import QSettings

# Landing page's own Vercel deployment also hosts this API route (see
# docs/api/activate.js) -- same project, no separate service to run/pay for.
ACTIVATION_ENDPOINT = "https://getvoxscribe.vercel.app/api/activate"

# Public half of the signing keypair -- safe to embed/commit. The matching
# private key lives only in the untracked license_signing_key.raw.
_PUBLIC_KEY_HEX = "3c99649247537fb1a3ecd9e7ba0987ee1c3bdae92b911dae9eeb58095b3e2edc"

_LICENSE_ID_LEN = 8
_SIGNATURE_LEN = 64

_public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(_PUBLIC_KEY_HEX))


def _settings() -> QSettings:
    return QSettings("VoxScribe", "VoxScribe")


def format_key(raw: bytes) -> str:
    """raw = license_id (8 bytes) + signature (64 bytes) -> a
    human-typeable, dash-grouped key. Used by the (dev-only) key generator;
    kept here so the format is defined in exactly one place."""
    encoded = base64.b32encode(raw).decode("ascii").rstrip("=")
    return "-".join(encoded[i : i + 8] for i in range(0, len(encoded), 8))


def verify_license_key(key: str) -> bool:
    """True if `key` is a validly signed license key. Purely a signature
    check -- no network call, no account, works offline."""
    cleaned = key.strip().replace("-", "").replace(" ", "").upper()
    padded = cleaned + "=" * (-len(cleaned) % 8)
    try:
        raw = base64.b32decode(padded)
    except (ValueError, base64.binascii.Error):  # noqa: BLE001
        return False

    if len(raw) != _LICENSE_ID_LEN + _SIGNATURE_LEN:
        return False

    license_id, signature = raw[:_LICENSE_ID_LEN], raw[_LICENSE_ID_LEN:]
    try:
        _public_key.verify(signature, license_id)
    except InvalidSignature:
        return False
    return True


def is_pro() -> bool:
    """Whether a valid Pro license key is currently stored. Cheap enough
    (one Ed25519 verify, no I/O beyond QSettings) to call freely rather
    than caching -- avoids a stale-cache class of bug if the key ever
    changes mid-session."""
    stored = _settings().value("license_key", "")
    return bool(stored) and verify_license_key(stored)


def set_license_key(key: str) -> bool:
    """Validates and stores `key`. Returns whether it was valid -- an
    invalid key is never persisted, so a typo can't silently "unlock"
    nothing while looking saved."""
    if not verify_license_key(key):
        return False
    _settings().setValue("license_key", key.strip())
    return True


def clear_license_key() -> None:
    _settings().remove("license_key")


def _hardware_id() -> str:
    """A hardware-derived id (SMBIOS/BIOS system UUID), not tied to the
    Windows *installation* -- unlike a registry-generated machine GUID,
    this stays the same across a Windows reinstall on the same physical
    machine, matching how a real customer actually uses their PC (see the
    LittlePooky Reddit thread this was built for). Falls back to "unknown"
    if it can't be read (e.g. inside some VMs, or wmic/CIM unavailable);
    the activation endpoint treats "unknown" as its own bucket rather than
    failing, since a handful of users sharing that value is an acceptable
    edge case for what's meant to be a light deterrent, not real DRM."""
    try:
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-NonInteractive", "-Command",
                "(Get-CimInstance Win32_ComputerSystemProduct).UUID",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        value = result.stdout.strip()
        return value if value else "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def activate_online(key: str, timeout: float = 8.0) -> tuple[bool, str]:
    """Check/claim `key` against the online activation registry (see this
    module's docstring). Returns (ok, message) -- message is a short,
    user-facing reason on failure, or a status word on success.

    This is the only network call VoxScribe's licensing makes; is_pro()
    never calls this and stays fully offline. Call this once, from the
    Settings dialog's Unlock button, before persisting the key locally
    with set_license_key().
    """
    if not verify_license_key(key):
        return False, "That key isn't valid -- check for typos and try again."

    payload = json.dumps({"key": key.strip(), "hardware_id": _hardware_id()}).encode("utf-8")
    request = urllib.request.Request(
        ACTIVATION_ENDPOINT,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
            return bool(data.get("ok")), data.get("message", "")
    except urllib.error.HTTPError as exc:
        try:
            data = json.loads(exc.read().decode("utf-8"))
            return False, data.get("message", f"Activation server error ({exc.code}).")
        except Exception:  # noqa: BLE001
            return False, f"Activation server error ({exc.code})."
    except Exception as exc:  # noqa: BLE001
        return False, f"Couldn't reach the activation server: {exc}"
