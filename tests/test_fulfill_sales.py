"""Tests for scripts/fulfill_sales.py: one key per paid sale, retries, filtering.
No real network, email or signing key is touched: everything is passed in as fakes."""

import importlib.util
import json
import smtplib
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "fulfill_sales.py"
import sys

spec = importlib.util.spec_from_file_location("fulfill_sales", SCRIPT)
fs = importlib.util.module_from_spec(spec)
sys.modules["fulfill_sales"] = fs
spec.loader.exec_module(fs)


def raw(sale_id="s1", email="a@example.com", product="VoxScribe Pro", created="2026-10-12", **kw):
    return {"id": sale_id, "email": email, "product_name": product, "created_at": created, **kw}


def sale(**kw) -> "fs.Sale":
    return fs.parse_sale(raw(**kw))


class Recorder:
    """Stands in for key issuing, the sales log and email delivery."""

    def __init__(self, fail_delivery: bool = False):
        self.keys: list[str] = []
        self.logged: list[tuple[str, str]] = []
        self.delivered: list[tuple[str, str]] = []
        self.fail_delivery = fail_delivery
        self.saved_states: list[str] = []

    def issue(self) -> str:
        key = f"KEY-{len(self.keys) + 1}"
        self.keys.append(key)
        return key

    def log(self, buyer: str, key: str) -> None:
        self.logged.append((buyer, key))

    def deliver(self, s, key: str) -> str:
        if self.fail_delivery:
            raise smtplib.SMTPException("mail is down")
        self.delivered.append((s.email, key))
        return "sent"

    def save(self, state: dict) -> None:
        self.saved_states.append(json.dumps(state))


def run(sales, state, rec: Recorder):
    return fs.fulfil(sales, state, rec.issue, rec.log, rec.deliver, rec.save)


def test_parse_sale_needs_an_id_and_an_email():
    assert fs.parse_sale({"email": "a@b.c"}) is None
    assert fs.parse_sale({"id": "x", "email": " "}) is None
    parsed = fs.parse_sale(raw(refunded=True))
    assert parsed.refunded and parsed.email == "a@example.com"


def test_only_paid_unhandled_pro_sales_are_pending_oldest_first():
    sales = [
        sale(sale_id="new2", created="2026-10-12"),
        sale(sale_id="new1", created="2026-10-11"),
        sale(sale_id="refunded", refunded=True),
        sale(sale_id="other", product="Some Other Product"),
        sale(sale_id="done"),
    ]

    result = fs.pending(sales, {"done": {"key": "K", "delivered": "sent"}})

    assert [s.id for s in result] == ["new1", "new2"]


def test_each_sale_gets_one_key_and_one_email():
    rec = Recorder()
    state: dict = {}

    results = run([sale(sale_id="s1"), sale(sale_id="s2", email="b@example.com")], state, rec)

    assert rec.keys == ["KEY-1", "KEY-2"]
    assert rec.delivered == [("a@example.com", "KEY-1"), ("b@example.com", "KEY-2")]
    assert [outcome for _s, outcome in results] == ["sent", "sent"]
    assert rec.logged[0][0] == "a@example.com (Gumroad sale s1)"


def test_running_again_does_nothing_new():
    rec = Recorder()
    state: dict = {}
    run([sale()], state, rec)

    again = run([sale()], state, rec)

    assert again == []
    assert rec.keys == ["KEY-1"] and len(rec.delivered) == 1


def test_a_failed_email_is_retried_with_the_same_key():
    rec = Recorder(fail_delivery=True)
    state: dict = {}
    first = run([sale()], state, rec)
    assert first[0][1].startswith("FAILED")
    assert state["s1"]["delivered"] is None

    rec.fail_delivery = False
    second = run([sale()], state, rec)

    assert second[0][1] == "sent"
    assert rec.keys == ["KEY-1"]
    assert rec.delivered == [("a@example.com", "KEY-1")]


def test_the_key_is_saved_before_delivery_is_attempted():
    rec = Recorder(fail_delivery=True)
    state: dict = {}
    run([sale()], state, rec)

    assert json.loads(rec.saved_states[0])["s1"]["key"] == "KEY-1"


def test_a_refunded_sale_gets_nothing():
    rec = Recorder()

    assert run([sale(refunded=True)], {}, rec) == []
    assert rec.keys == []


def test_existing_marked_sales_are_never_issued_or_delivered():
    rec = Recorder()
    state = {"s1": {"email": "a@example.com", "key": None, "delivered": "existing"}}

    assert run([sale()], state, rec) == []
    assert rec.keys == []


def test_fetch_follows_next_page_url():
    pages = {
        f"{fs.API_BASE}/v2/sales": {
            "success": True,
            "sales": [raw("p1")],
            "next_page_url": "/v2/sales?page_key=2",
        },
        f"{fs.API_BASE}/v2/sales?page_key=2": {"success": True, "sales": [raw("p2")]},
    }

    sales = fs.fetch_sales("token", get=lambda url, _token: pages[url])

    assert [s.id for s in sales] == ["p1", "p2"]


def test_fetch_stops_with_a_clear_message_when_gumroad_says_no():
    with pytest.raises(SystemExit, match="refused"):
        fs.fetch_sales("token", get=lambda *_: {"success": False, "message": "bad token"})


def test_the_email_contains_the_key_and_both_platforms():
    subject, body = fs.compose_email("ABCD-EFGH")

    assert "ABCD-EFGH" in body
    assert "Windows" in body and "Android" in body
    assert "VoxScribe Pro" in subject
    assert "—" not in body and "–" not in body


def test_env_file_is_parsed(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('# comment\nGUMROAD_ACCESS_TOKEN="abc"\nOTHER=1\n', encoding="utf-8")
    monkeypatch.delenv("GUMROAD_ACCESS_TOKEN", raising=False)

    assert fs.load_env(env)["GUMROAD_ACCESS_TOKEN"] == "abc"
