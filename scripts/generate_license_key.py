"""Dev-only: issue a new VoxScribe Pro license key.

Run this yourself after a sale to generate the key you send the buyer (or let
scripts/fulfill_sales.py do it for new Gumroad sales).
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
    venv\\Scripts\\python.exe scripts\\generate_license_key.py --yearly "Buyer name"
    venv\\Scripts\\python.exe scripts\\generate_license_key.py --expires 2027-11-22 "Buyer name"

A yearly key only works in app versions that know the 74 byte key format, so
don't hand one out until those versions are released.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.license import expiry_to_bytes, format_key, license_expiry, verify_license_key

_KEY_FILE = Path(__file__).resolve().parent.parent / "license_signing_key.raw"
_SALES_LOG = Path(__file__).resolve().parent.parent / "sold_keys.csv"


def log_sale(buyer: str, key: str) -> None:
    """Appends a row to sold_keys.csv, the personal sales record."""
    is_new = not _SALES_LOG.exists()
    with _SALES_LOG.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["date_utc", "buyer", "key"])
        writer.writerow([datetime.now(timezone.utc).isoformat(timespec="seconds"), buyer, key])


def issue_key(expires: date | None = None) -> str:
    """Signs a fresh license id with the private key and returns the typeable key.
    No `expires` makes a perpetual key (the $14 one-time kind); with a date it
    makes a yearly key that stops unlocking Pro after that day.
    Raises FileNotFoundError if license_signing_key.raw is missing."""
    private_key = Ed25519PrivateKey.from_private_bytes(_KEY_FILE.read_bytes())
    license_id = os.urandom(8)
    if expires is None:
        raw = license_id + private_key.sign(license_id)
    else:
        expiry_bytes = expiry_to_bytes(expires)
        raw = license_id + expiry_bytes + private_key.sign(license_id + expiry_bytes)
    key = format_key(raw)
    assert verify_license_key(key), "generated key failed its own verification -- bug"
    assert license_expiry(key) == expires, "generated key has the wrong expiry -- bug"
    return key


def yearly_expiry(start: date | None = None) -> date:
    """The last valid day of a yearly key bought on `start` (default today):
    one year later, plus a 7 day grace so a slow renewal doesn't cut anyone off."""
    start = start or date.today()
    try:
        anniversary = start.replace(year=start.year + 1)
    except ValueError:  # 29 February
        anniversary = start.replace(year=start.year + 1, day=28)
    return anniversary + timedelta(days=7)


def main() -> None:
    parser = argparse.ArgumentParser(description="Issue a VoxScribe Pro license key.")
    parser.add_argument("buyer", nargs="*", help="buyer name or handle, logged to sold_keys.csv")
    parser.add_argument(
        "--yearly",
        action="store_true",
        help="make a yearly key (valid one year plus 7 days) instead of a perpetual one",
    )
    parser.add_argument("--expires", help="make a yearly key valid through this date, YYYY-MM-DD")
    args = parser.parse_args()

    expires = None
    if args.expires:
        expires = date.fromisoformat(args.expires)
    elif args.yearly:
        expires = yearly_expiry()

    try:
        key = issue_key(expires)
    except FileNotFoundError:
        print(f"Missing {_KEY_FILE} -- see this script's docstring.")
        raise SystemExit(1) from None
    print(key)
    print(f"Valid through {expires}" if expires else "Perpetual key (no expiry)")

    buyer = " ".join(args.buyer).strip()
    if buyer:
        log_sale(buyer, key)
        print(f"Logged to {_SALES_LOG.name} for buyer: {buyer}")


if __name__ == "__main__":
    main()
