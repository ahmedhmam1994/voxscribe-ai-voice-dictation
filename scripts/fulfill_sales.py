"""Dev-only: hands out VoxScribe Pro keys for new Gumroad sales.

For every new, paid sale of VoxScribe Pro it makes a license key, records it in
sold_keys.csv, and emails the buyer. The signing key (license_signing_key.raw)
never leaves this PC. Each sale gets exactly one key: the sale id is stored in
fulfilled_sales.json, and a key that could not be emailed is retried on the next
run with the same key instead of making a new one.

One-time setup, in the repo's .env file (git-ignored, never committed):

    GUMROAD_ACCESS_TOKEN=...   Gumroad > Settings > Advanced > Applications,
                               create an application, generate an access token
    GMAIL_ADDRESS=you@gmail.com        (optional, to email buyers directly)
    GMAIL_APP_PASSWORD=xxxx xxxx xxxx  (a Google app password, not your login)

Without the two Gmail lines the script still works: it saves each email as a text
file in fulfilled/ so you can paste it into a reply yourself.

Usage (from the repo root):

    python scripts\\fulfill_sales.py --check          test the token, change nothing
    python scripts\\fulfill_sales.py --mark-existing  once: past sales are handled
    python scripts\\fulfill_sales.py --dry-run        show what would be sent
    python scripts\\fulfill_sales.py                  do it

(use venv\\Scripts\\python.exe for "python")

To run it every 15 minutes, add a Windows scheduled task for the last command.
"""

from __future__ import annotations

import argparse
import json
import os
import smtplib
import ssl
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "fulfilled_sales.json"
OUTBOX = ROOT / "fulfilled"
API_BASE = "https://api.gumroad.com"
PRODUCT_NAME = "VoxScribe Pro"
RELEASES_URL = "https://github.com/ahmedhmam1994/voxscribe-ai-voice-dictation/releases"
MAX_PAGES = 50


@dataclass(frozen=True)
class Sale:
    id: str
    email: str
    product: str
    created_at: str
    refunded: bool


def load_env(path: Path = ROOT / ".env") -> dict[str, str]:
    """KEY=VALUE lines from the .env file, overridden by real environment variables."""
    values: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                name, _, value = line.partition("=")
                values[name.strip()] = value.strip().strip('"').strip("'")
    for name in ("GUMROAD_ACCESS_TOKEN", "GMAIL_ADDRESS", "GMAIL_APP_PASSWORD"):
        if os.environ.get(name):
            values[name] = os.environ[name]
    return values


def parse_sale(raw: dict) -> Sale | None:
    """One sale from the API, or None if it lacks an id or an email."""
    sale_id, email = raw.get("id"), (raw.get("email") or "").strip()
    if not sale_id or not email:
        return None
    return Sale(
        id=str(sale_id),
        email=email,
        product=str(raw.get("product_name") or ""),
        created_at=str(raw.get("created_at") or ""),
        refunded=bool(raw.get("refunded") or raw.get("chargedback") or raw.get("disputed")),
    )


def _http_get(url: str, token: str) -> dict:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 -- fixed host
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Gumroad said HTTP {exc.code}. Check GUMROAD_ACCESS_TOKEN.") from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise SystemExit(f"Could not reach Gumroad: {exc}") from exc


def fetch_sales(token: str, get: Callable[[str, str], dict] = _http_get) -> list[Sale]:
    """Every sale on the account, following the API's paging."""
    sales: list[Sale] = []
    url: str | None = f"{API_BASE}/v2/sales"
    for _ in range(MAX_PAGES):
        if not url:
            break
        data = get(url, token)
        if not data.get("success", True):
            raise SystemExit(f"Gumroad refused the request: {data.get('message', 'unknown error')}")
        sales += [s for raw in data.get("sales", []) if (s := parse_sale(raw))]
        next_url = data.get("next_page_url")
        url = f"{API_BASE}{next_url}" if next_url and next_url.startswith("/") else next_url
    return sales


def pending(sales: list[Sale], state: dict[str, dict]) -> list[Sale]:
    """Paid, unhandled sales of the Pro product, oldest first."""
    wanted = [
        s
        for s in sales
        if PRODUCT_NAME.lower() in s.product.lower() and not s.refunded and s.id not in state
    ]
    return sorted(wanted, key=lambda s: s.created_at)


def compose_email(key: str) -> tuple[str, str]:
    """(subject, body) for the buyer."""
    subject = "Your VoxScribe Pro license key"
    body = f"""Hi,

Thanks for buying VoxScribe Pro. Here is your license key:

{key}

To unlock it on Windows: open VoxScribe, go to Settings, find the license section near the top, paste the key and click Unlock. It needs an internet connection that one time, and after that Pro works offline.

The same key also works on the Android app (one Windows PC and one Android phone). On the phone, open the app, go to Settings, then VoxScribe Pro, and paste it there. The Android app is a separate download on the releases page: {RELEASES_URL}

If it says the key is already activated, or anything else looks wrong, just reply to this email and I will sort it out.

Thanks again for supporting it.

Ahmed
"""  # noqa: E501
    return subject, body


def send_smtp(address: str, password: str, to: str, subject: str, body: str) -> None:
    message = EmailMessage()
    message["From"] = address
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as server:
        server.login(address, password.replace(" ", ""))
        server.send_message(message)


def save_to_outbox(sale: Sale, subject: str, body: str) -> Path:
    OUTBOX.mkdir(exist_ok=True)
    path = OUTBOX / f"{sale.id.strip('=').replace('/', '_')}.txt"
    path.write_text(f"To: {sale.email}\nSubject: {subject}\n\n{body}", encoding="utf-8")
    return path


def load_state() -> dict[str, dict]:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state: dict[str, dict]) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def fulfil(
    sales: list[Sale],
    state: dict[str, dict],
    issue_key: Callable[[], str],
    log_sale: Callable[[str, str], None],
    deliver: Callable[[Sale, str], str],
    save: Callable[[dict[str, dict]], None] = save_state,
) -> list[tuple[Sale, str]]:
    """Issues a key for each pending sale and delivers it. Returns (sale, outcome) pairs.

    A key is recorded in `state` the moment it exists, before delivery, so a failed
    email is retried later with the same key and a sale never gets two keys."""
    results: list[tuple[Sale, str]] = []
    by_id = {s.id: s for s in sales}
    for sale in pending(sales, state):
        key = issue_key()
        log_sale(f"{sale.email} (Gumroad sale {sale.id})", key)
        state[sale.id] = {"email": sale.email, "key": key, "delivered": None}
        save(state)
    for sale_id, entry in state.items():
        if entry.get("delivered") is None and sale_id in by_id:
            try:
                entry["delivered"] = deliver(by_id[sale_id], entry["key"])
                outcome = entry["delivered"]
            except (OSError, smtplib.SMTPException) as exc:
                outcome = f"FAILED, will retry: {exc}"
            save(state)
            results.append((by_id[sale_id], outcome))
    return results


def _deliver_factory(env: dict[str, str]) -> Callable[[Sale, str], str]:
    def deliver(sale: Sale, key: str) -> str:
        subject, body = compose_email(key)
        address, password = env.get("GMAIL_ADDRESS"), env.get("GMAIL_APP_PASSWORD")
        if address and password:
            send_smtp(address, password, sale.email, subject, body)
            return "sent"
        return f"saved to {save_to_outbox(sale, subject, body).relative_to(ROOT)}"

    return deliver


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hand out Pro keys for new Gumroad sales.")
    parser.add_argument("--check", action="store_true", help="test the token and show counts")
    parser.add_argument("--dry-run", action="store_true", help="show pending sales, change nothing")
    parser.add_argument(
        "--mark-existing", action="store_true", help="treat all current sales as already handled"
    )
    args = parser.parse_args(argv)

    env = load_env()
    token = env.get("GUMROAD_ACCESS_TOKEN")
    if not token:
        print("GUMROAD_ACCESS_TOKEN is missing from .env. See this script's docstring.")
        return 1

    sales = fetch_sales(token)
    state = load_state()
    waiting = pending(sales, state)

    if args.check:
        print(f"Connected. {len(sales)} sales on the account, {len(waiting)} waiting for a key.")
        return 0
    if args.mark_existing:
        for sale in sales:
            state.setdefault(sale.id, {"email": sale.email, "key": None, "delivered": "existing"})
        save_state(state)
        print(f"Marked {len(sales)} existing sales as handled.")
        return 0
    if args.dry_run:
        for sale in waiting:
            print(f"would send a key to {sale.email} (sale {sale.id}, {sale.created_at})")
        print(f"{len(waiting)} sale(s) waiting.")
        return 0

    from generate_license_key import issue_key, log_sale

    try:
        results = fulfil(sales, state, issue_key, log_sale, _deliver_factory(env))
    except FileNotFoundError:
        print("license_signing_key.raw is missing, so no keys can be made.")
        return 1
    for sale, outcome in results:
        print(f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} {sale.email}: {outcome}")
    if not results:
        print("Nothing new.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
