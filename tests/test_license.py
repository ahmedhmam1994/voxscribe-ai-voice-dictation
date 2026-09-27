"""Tests for core/license.py's offline verification and online activation."""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.license import activate_online, format_key, verify_license_key


def _make_valid_key() -> str:
    private_key = Ed25519PrivateKey.from_private_bytes(os.urandom(32))
    license_id = os.urandom(8)
    signature = private_key.sign(license_id)
    return format_key(license_id + signature)


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
