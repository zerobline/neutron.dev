import time
from unittest.mock import patch

import pytest

from app.auth.rate_limit import (
    MAX_ATTEMPTS,
    WINDOW_SECONDS,
    _CLEANUP_INTERVAL,
    _client_ip,
    check_rate_limit,
    reset_rate_limits,
)
from fastapi import HTTPException, Request


def _make_request(ip: str = "1.2.3.4", forwarded: str | None = None) -> Request:
    scope = {"type": "http", "headers": [], "client": (ip, 0)}
    if forwarded:
        scope["headers"] = [(b"x-forwarded-for", forwarded.encode())]
    return Request(scope)


@pytest.fixture(autouse=True)
def _reset():
    reset_rate_limits()
    yield
    reset_rate_limits()


def test_allows_up_to_max_attempts():
    for _ in range(MAX_ATTEMPTS):
        check_rate_limit(_make_request())


def test_blocks_after_max_attempts():
    for _ in range(MAX_ATTEMPTS):
        check_rate_limit(_make_request())
    with pytest.raises(HTTPException) as exc_info:
        check_rate_limit(_make_request())
    assert exc_info.value.status_code == 429


def test_different_ips_tracked_independently():
    for _ in range(MAX_ATTEMPTS):
        check_rate_limit(_make_request("1.2.3.4"))
    check_rate_limit(_make_request("5.6.7.8"))


def test_window_expires():
    future = time.monotonic() + WINDOW_SECONDS + 1
    for _ in range(MAX_ATTEMPTS):
        check_rate_limit(_make_request())
    with patch("app.auth.rate_limit.time.monotonic", return_value=future):
        check_rate_limit(_make_request())


def test_client_ip_from_x_forwarded_for():
    req = _make_request(forwarded="10.0.0.1, 10.0.0.2")
    assert _client_ip(req) == "10.0.0.1"


def test_client_ip_falls_back_to_client_host():
    req = _make_request("9.8.7.6")
    assert _client_ip(req) == "9.8.7.6"


def test_client_ip_no_client():
    scope = {"type": "http", "headers": []}
    req = Request(scope)
    assert _client_ip(req) == "unknown"


def test_cleanup_removes_stale_entries():
    import app.auth.rate_limit as rl

    check_rate_limit(_make_request("1.1.1.1"))
    rl._last_cleanup = 0.0
    future = time.monotonic() + WINDOW_SECONDS + _CLEANUP_INTERVAL + 1
    with patch("app.auth.rate_limit.time.monotonic", return_value=future):
        check_rate_limit(_make_request("2.2.2.2"))
    assert "1.1.1.1" not in rl._attempts
