"""Runs the Node tests for tools/apps-script-fulfillment and checks that a key made by
the Apps Script code passes the same Python verifier the Windows app uses (core/license.py).
Skipped when Node is not installed."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import core.license as license_module

NODE = shutil.which("node")
TOOL = Path(__file__).resolve().parent.parent / "tools" / "apps-script-fulfillment"

pytestmark = pytest.mark.skipif(NODE is None, reason="Node is not installed")


def test_the_node_suite_passes():
    result = subprocess.run(
        [NODE, "--test", "test.js"], cwd=TOOL, capture_output=True, text=True, timeout=120
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_an_apps_script_key_passes_the_windows_verifier(monkeypatch):
    seed = os.urandom(32)
    monkeypatch.setattr(
        license_module, "_public_key", Ed25519PrivateKey.from_private_bytes(seed).public_key()
    )

    key = subprocess.run(
        [NODE, "test.js", "--emit-key", seed.hex()],
        cwd=TOOL,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    ).stdout.strip()

    assert license_module.verify_license_key(key)
    # Not the last character: a base32 key's final character carries just one real bit.
    changed = "A" if key[21] != "A" else "B"
    assert not license_module.verify_license_key(key[:21] + changed + key[22:])
