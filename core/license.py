"""Offline Pro-license verification.

VoxScribe stays free forever for its core dictation features -- this only
gates the Pro tier (snippets/macros, see core/snippets.py, and future Pro
features). Verification works fully offline, with no server/account and
nothing phoning home: a license key is a signed blob, verified locally
against a public key embedded in this file. Signing itself happens outside
this app entirely, with a private key that never ships (see
scripts/generate_license_key.py and .gitignore's note on
license_signing_key.raw) -- this module can only verify keys, never mint
them.

Key format: base32(license_id[8 bytes] || Ed25519 signature[64 bytes]),
grouped into dash-separated blocks for readability. There's no expiry or
per-seat check baked into the key itself -- a valid key is a perpetual,
single unlock, matching a one-time-purchase Pro tier rather than a
subscription.
"""

from __future__ import annotations

import base64

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from PySide6.QtCore import QSettings

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
