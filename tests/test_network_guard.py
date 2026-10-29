"""Tests for core/network_guard.py. The socket functions are replaced with
fakes first, so no test ever touches the real network."""

import socket

import pytest

import core.network_guard as guard


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(guard, "LOG_PATH", tmp_path / "network_log.jsonl")
    monkeypatch.setattr(guard, "_original_getaddrinfo", lambda *a, **k: [("fake",)])
    monkeypatch.setattr(guard, "_original_connect", lambda self, address: None)
    guard.install()
    yield
    guard.uninstall()


def test_a_lookup_is_logged_while_offline_mode_is_off():
    assert socket.getaddrinfo("example.com", 443) == [("fake",)]

    entries = guard.recent()
    assert [(e.host, e.blocked) for e in entries] == [("example.com", False)]


def test_offline_mode_blocks_and_logs_a_lookup():
    guard.set_blocking(True)

    with pytest.raises(OSError, match="offline mode is on"):
        socket.getaddrinfo("us.i.posthog.com", 443)

    assert [(e.host, e.blocked) for e in guard.recent()] == [("us.i.posthog.com", True)]


def test_offline_mode_blocks_a_direct_connection():
    guard.set_blocking(True)

    with pytest.raises(OSError, match="offline mode is on"):
        socket.socket.connect(object(), ("93.184.216.34", 443))


def test_this_pc_is_never_blocked_or_logged():
    guard.set_blocking(True)

    assert socket.getaddrinfo("localhost", 80) == [("fake",)]
    socket.socket.connect(object(), ("127.0.0.1", 80))
    assert guard.recent() == []


def test_turning_the_block_off_lets_traffic_through_again():
    guard.set_blocking(True)
    guard.set_blocking(False)

    assert socket.getaddrinfo("example.com", 443) == [("fake",)]


def test_is_local():
    assert guard.is_local("localhost")
    assert guard.is_local("127.0.0.1")
    assert guard.is_local("::1")
    assert guard.is_local(None)
    assert not guard.is_local("example.com")
    assert not guard.is_local("192.168.0.101")


def test_the_log_is_newest_first_and_can_be_cleared():
    socket.getaddrinfo("first.example", 443)
    socket.getaddrinfo("second.example", 443)

    assert [e.host for e in guard.recent()] == ["second.example", "first.example"]
    guard.clear_log()
    assert guard.recent() == []


def test_a_huge_log_is_trimmed(monkeypatch):
    monkeypatch.setattr(guard, "_MAX_LOG_BYTES", 500)
    for i in range(60):
        socket.getaddrinfo(f"host{i}.example", 443)

    assert len(guard.recent(1000)) <= guard._KEEP_LINES
    assert guard.recent(1)[0].host == "host59.example"


def test_count_since_counts_only_recent_attempts():
    import time

    guard._record("old.example", False)
    time.sleep(0.02)
    mark = time.time()
    assert guard.count_since(mark) == 0
    guard._record("a.example", False)
    guard._record("b.example", True)
    assert guard.count_since(mark) == 2
