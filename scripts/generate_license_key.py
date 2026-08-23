"""Dev-only: issue a new VoxScribe Pro license key.

Run this yourself after a sale to generate the key you send the buyer.
Requires license_signing_key.raw at the repo root (gitignored, never
shipped with the app -- see core/license.py's module docstring). Losing
that file means you can never issue new keys again; regenerate a fresh
keypair only as an absolute last resort, since it invalidates every
key already sold (core/license.py's embedded public key would need to
change too).

Usage:
    venv\\Scripts\\python.exe scripts\\generate_license_key.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.license import format_key, verify_license_key

_KEY_FILE = Path(__file__).resolve().parent.parent / "license_signing_key.raw"


def main() -> None:
    if not _KEY_FILE.exists():
        print(f"Missing {_KEY_FILE} -- see this script's docstring.")
        raise SystemExit(1)

    private_key = Ed25519PrivateKey.from_private_bytes(_KEY_FILE.read_bytes())
    license_id = os.urandom(8)
    signature = private_key.sign(license_id)
    key = format_key(license_id + signature)

    assert verify_license_key(key), "generated key failed its own verification -- bug"
    print(key)


if __name__ == "__main__":
    main()
