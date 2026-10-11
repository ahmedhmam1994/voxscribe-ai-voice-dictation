"""Proven offline mode -- a Pro feature (see core/license.py).

Two jobs, both at the lowest level Python offers so no library can slip past:

1. A log of every host this process looks up or connects to, kept in a small
   file on this PC. It is the evidence behind "your audio never leaves your
   machine": with the launch ping, update check and model download switched
   off, the log stays empty.
2. A switch that blocks all of it. While offline mode is on, any attempt to
   reach a non-local host fails immediately with an OSError, so the launch
   ping, the update check and the model download simply do not happen.

It wraps `socket.getaddrinfo` (every lookup by name) and `socket.socket.connect`
(direct connections to an address). Connections to this PC itself (localhost
and loopback addresses) are never blocked or logged, since Qt and tests use them.
"""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import threading
import time
from dataclasses import dataclass
from pathlib import Path

_APP_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "VoxScribe"
LOG_PATH = _APP_DIR / "network_log.jsonl"
_MAX_LOG_BYTES = 200_000
_KEEP_LINES = 300

_lock = threading.Lock()
_blocking = False
_installed = False
_original_getaddrinfo = socket.getaddrinfo
_original_connect = socket.socket.connect


@dataclass(frozen=True)
class Connection:
    when: float
    host: str
    blocked: bool


def is_local(host: object) -> bool:
    """True for this PC itself: localhost, loopback addresses, empty host."""
    if host is None or host == "":
        return True
    if isinstance(host, bytes):
        host = host.decode("ascii", "ignore")
    if not isinstance(host, str):
        return True
    if host.lower() in {"localhost", "localhost.localdomain"}:
        return True
    try:
        return ipaddress.ip_address(host.split("%")[0]).is_loopback
    except ValueError:
        return False


def set_blocking(blocking: bool) -> None:
    """Turns the block on or off. Takes effect for the next connection."""
    global _blocking
    _blocking = blocking


def is_blocking() -> bool:
    return _blocking


def _record(host: str, blocked: bool) -> None:
    line = json.dumps({"t": time.time(), "host": host, "blocked": blocked})
    try:
        with _lock:
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with LOG_PATH.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
            _trim_locked()
    except OSError:
        # Logging must never break a connection or the app.
        pass


def _trim_locked() -> None:
    if LOG_PATH.stat().st_size <= _MAX_LOG_BYTES:
        return
    lines = LOG_PATH.read_text(encoding="utf-8").splitlines()[-_KEEP_LINES:]
    LOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _refuse(host: str) -> OSError:
    return OSError(f"VoxScribe offline mode is on, so it cannot reach {host}.")


def _guarded_getaddrinfo(host, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN202
    if not is_local(host):
        name = host.decode("ascii", "ignore") if isinstance(host, bytes) else str(host)
        _record(name, _blocking)
        if _blocking:
            raise _refuse(name)
    return _original_getaddrinfo(host, *args, **kwargs)


def _guarded_connect(self, address):  # noqa: ANN001, ANN202
    if _blocking and isinstance(address, tuple) and address and not is_local(address[0]):
        _record(str(address[0]), True)
        raise _refuse(str(address[0]))
    return _original_connect(self, address)


def install() -> None:
    """Starts logging and enforcing. Safe to call more than once."""
    global _installed
    if _installed:
        return
    socket.getaddrinfo = _guarded_getaddrinfo
    socket.socket.connect = _guarded_connect
    _installed = True


def uninstall() -> None:
    """Puts the original socket functions back. Used by tests."""
    global _installed, _blocking
    socket.getaddrinfo = _original_getaddrinfo
    socket.socket.connect = _original_connect
    _installed = False
    _blocking = False


def recent(limit: int = 100) -> list[Connection]:
    """The latest logged connections, newest first."""
    try:
        lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    entries: list[Connection] = []
    for line in reversed(lines):
        try:
            item = json.loads(line)
            entries.append(Connection(float(item["t"]), str(item["host"]), bool(item["blocked"])))
        except (ValueError, KeyError, TypeError):
            continue
        if len(entries) >= limit:
            break
    return entries


def clear_log() -> None:
    try:
        with _lock:
            LOG_PATH.unlink(missing_ok=True)
    except OSError:
        pass
