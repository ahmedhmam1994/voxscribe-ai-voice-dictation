"""Tests for core/license.py's offline verification and online activation."""

from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import core.license as license_module
from core.license import (
    activate_online,
    expiry_to_bytes,
    format_key,
    is_expired,
    is_pro,
    license_expiry,
    set_license_key,
    verify_license_key,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


def _make_valid_key() -> str:
    private_key = Ed25519PrivateKey.from_private_bytes(os.urandom(32))
    license_id = os.urandom(8)
    signature = private_key.sign(license_id)
    return format_key(license_id + signature)


@pytest.fixture
def signer(monkeypatch):
    """A throwaway signing key, swapped in for the app's embedded public key so
    tests can mint keys without the real private key."""
    private_key = Ed25519PrivateKey.from_private_bytes(os.urandom(32))
    monkeypatch.setattr(license_module, "_public_key", private_key.public_key())
    return private_key


def _perpetual_key(private_key) -> str:
    license_id = os.urandom(8)
    return format_key(license_id + private_key.sign(license_id))


def _yearly_key(private_key, expires: date) -> str:
    license_id = os.urandom(8)
    expiry = expiry_to_bytes(expires)
    return format_key(license_id + expiry + private_key.sign(license_id + expiry))


def test_perpetual_key_still_verifies_and_never_expires(signer):
    key = _perpetual_key(signer)
    assert verify_license_key(key) is True
    assert license_expiry(key) is None
    assert is_expired(key, today=date(2099, 1, 1)) is False


def test_yearly_key_verifies_and_reports_its_expiry(signer):
    key = _yearly_key(signer, date(2027, 11, 22))
    assert verify_license_key(key) is True
    assert license_expiry(key) == date(2027, 11, 22)


def test_yearly_key_works_through_its_last_day_then_expires(signer):
    key = _yearly_key(signer, date(2027, 11, 22))
    assert is_expired(key, today=date(2027, 11, 22)) is False
    assert is_expired(key, today=date(2027, 11, 23)) is True


def test_tampered_expiry_is_rejected(signer):
    # Anyone could re-encode a yearly key with a later date; the signature
    # covers the date, so that must not verify.
    key = _yearly_key(signer, date(2027, 11, 22))
    raw = bytearray(license_module._decode_key(key))
    raw[8:10] = expiry_to_bytes(date(2035, 1, 1))
    assert verify_license_key(format_key(bytes(raw))) is False


def test_key_of_unknown_length_is_rejected(signer):
    key = _perpetual_key(signer)
    raw = license_module._decode_key(key)
    assert verify_license_key(format_key(raw + b"\x00")) is False
    assert verify_license_key(format_key(raw[:-1])) is False


def test_set_license_key_refuses_an_expired_key(signer):
    key = _yearly_key(signer, date(2020, 1, 1))
    assert set_license_key(key) is False


def test_is_pro_is_false_for_a_stored_expired_key(signer):
    stored = MagicMock()
    stored.value.return_value = _yearly_key(signer, date(2020, 1, 1))
    with patch("core.license._settings", return_value=stored):
        assert is_pro() is False


def test_is_pro_is_true_for_a_stored_unexpired_yearly_key(signer):
    stored = MagicMock()
    stored.value.return_value = _yearly_key(signer, date.today() + timedelta(days=30))
    with patch("core.license._settings", return_value=stored):
        assert is_pro() is True


def test_activate_online_names_the_expiry_date_for_an_expired_key(signer):
    key = _yearly_key(signer, date(2026, 1, 5))
    with patch("core.license.urllib.request.urlopen") as mock_urlopen:
        ok, message = activate_online(key)
    assert ok is False
    assert "expired" in message and "05 January 2026" in message
    mock_urlopen.assert_not_called()


def test_generated_yearly_key_round_trips(monkeypatch, tmp_path, signer):
    import generate_license_key as generator

    key_file = tmp_path / "license_signing_key.raw"
    key_file.write_bytes(signer.private_bytes_raw())
    monkeypatch.setattr(generator, "_KEY_FILE", key_file)

    assert license_expiry(generator.issue_key(date(2027, 11, 22))) == date(2027, 11, 22)
    assert license_expiry(generator.issue_key()) is None


def test_yearly_expiry_is_one_year_plus_seven_days():
    import generate_license_key as generator

    assert generator.yearly_expiry(date(2026, 11, 15)) == date(2027, 11, 22)
    assert generator.yearly_expiry(date(2028, 2, 29)) == date(2029, 3, 7)


def test_verify_rejects_garbage():
    assert verify_license_key("NOT-A-REAL-KEY") is False
    assert verify_license_key("") is False


def test_verify_rejects_key_signed_by_wrong_private_key():
    # Valid base32/length shape, but not actually signed by the app's
    # embedded public key -- must not be accepted.
    assert verify_license_key(_make_valid_key()) is False


def test_activate_online_rejects_invalid_key_without_network_call():
    with patch("core.license.urllib.request.urlopen") as mock_urlopen:
        ok, message = activate_online("NOT-A-REAL-KEY")
        assert ok is False
        assert "valid" in message.lower()
        mock_urlopen.assert_not_called()


def _fake_response(payload: dict):
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode("utf-8")
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return response


def test_activate_online_success():
    # A syntactically valid (but not app-signed) key is enough to reach the
    # network call, since real signature verification for a genuine sale
    # happens server-side too -- this test only checks the HTTP plumbing.
    fake_response = _fake_response({"ok": True, "message": "activated"})
    with patch("core.license.verify_license_key", return_value=True), \
         patch("core.license.urllib.request.urlopen", return_value=fake_response):
        ok, message = activate_online("ANYTHING")
        assert ok is True
        assert message == "activated"


def test_activate_online_reports_server_rejection():
    with patch("core.license.verify_license_key", return_value=True), \
         patch(
             "core.license.urllib.request.urlopen",
             return_value=_fake_response(
                 {"ok": False, "message": "This key is already activated on a different device."}
             ),
         ):
        ok, message = activate_online("ANYTHING")
        assert ok is False
        assert "already activated" in message


def test_activate_online_handles_network_failure():
    with patch("core.license.verify_license_key", return_value=True), \
         patch("core.license.urllib.request.urlopen", side_effect=OSError("no internet")):
        ok, message = activate_online("ANYTHING")
        assert ok is False
        assert "activation server" in message.lower()


def test_deactivate_online_sends_this_pc_and_the_deactivate_action():
    from core.license import deactivate_online

    sent = {}

    def fake_urlopen(request, timeout):
        sent.update(json.loads(request.data.decode("utf-8")))
        return _fake_response({"ok": True, "message": "deactivated"})

    with patch("core.license.verify_license_key", return_value=True), \
         patch("core.license._hardware_id", return_value="PC-UUID"), \
         patch("core.license.urllib.request.urlopen", side_effect=fake_urlopen):
        ok, message = deactivate_online("ANYTHING")
    assert ok is True
    assert sent["action"] == "deactivate"
    assert sent["hardware_id"] == "PC-UUID"


def test_deactivate_online_handles_network_failure():
    from core.license import deactivate_online

    with patch("core.license.verify_license_key", return_value=True), \
         patch("core.license.urllib.request.urlopen", side_effect=OSError("no internet")):
        ok, message = deactivate_online("ANYTHING")
    assert ok is False
