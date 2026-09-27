"""Dev-only: issue a new VoxScribe Pro license key.

Run this yourself after a sale to generate the key you send the buyer.
Requires license_signing_key.raw at the repo root (gitignored, never
shipped with the app -- see core/license.py's module docstring). Losing
that file means you can never issue new keys again; regenerate a fresh
keypair only as an absolute last resort, since it invalidates every
key already sold (core/license.py's embedded public key would need to
change too).

There's no server-side registry of issued keys -- verification is a pure
offline signature check (see core/license.py), so nothing here tracks
which keys have been issued or to whom. Pass a buyer name/handle as an
argument and this script will also append a row to sold_keys.csv (repo
root, gitignored) as your own personal sales record -- purely for your
own bookkeeping, the app never reads this file.

Usage:
    venv\\Scripts\\python.exe scripts\\generate_license_key.py
    venv\\Scripts\\python.exe scripts\\generate_license_key.py "LittlePooky (Reddit)"
"""

from __future__ import annotations

import csv
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.license import format_key, verify_license_key

_KEY_FILE = Path(__file__).resolve().parent.parent / "license_signing_key.raw"
_SALES_LOG = Path(__file__).resolve().parent.parent / "sold_keys.csv"


def _log_sale(buyer: str, key: str) -> None:
    is_new = not _SALES_LOG.exists()
    with _SALES_LOG.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["date_utc", "buyer", "key"])
        writer.writerow([datetime.now(timezone.utc).isoformat(timespec="seconds"), buyer, key])


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

    buyer = " ".join(sys.argv[1:]).strip()
    if buyer:
        _log_sale(buyer, key)
        print(f"Logged to {_SALES_LOG.name} for buyer: {buyer}")


if __name__ == "__main__":
    main()
