from unittest.mock import MagicMock

from app.auth.session import (
    extract_bearer_token,
    extract_session_token,
    extract_websocket_session_token,
)


def test_extract_bearer_token_handles_missing_and_invalid_headers():
    assert extract_bearer_token(None) is None
    assert extract_bearer_token("Token abc") is None
    assert extract_bearer_token("Bearer ") is None


def test_extract_bearer_token_parses_bearer_header():
    assert extract_bearer_token("Bearer session-token") == "session-token"
    assert extract_bearer_token("bearer another-token") == "another-token"


def test_extract_session_token_prefers_bearer_over_cookie():
    request = MagicMock()
    request.headers.get.return_value = "Bearer bearer-token"
    request.cookies.get.return_value = "cookie-token"

    assert extract_session_token(request) == "bearer-token"


def test_extract_session_token_falls_back_to_cookie():
    request = MagicMock()
    request.headers.get.return_value = None
    request.cookies.get.return_value = "cookie-token"

    assert extract_session_token(request) == "cookie-token"


def test_extract_websocket_session_token_prefers_query_param():
    ws = MagicMock()
    ws.query_params.get.return_value = "query-token"
    ws.cookies.get.return_value = "cookie-token"

    assert extract_websocket_session_token(ws) == "query-token"


def test_extract_websocket_session_token_falls_back_to_cookie():
    ws = MagicMock()
    ws.query_params.get.return_value = ""
    ws.cookies.get.return_value = "cookie-token"

    assert extract_websocket_session_token(ws) == "cookie-token"


def test_extract_session_token_ignores_invalid_cookies():
    request = MagicMock()
    request.headers.get.return_value = None
    request.cookies.get.return_value = ""

    assert extract_session_token(request) is None


def test_extract_websocket_session_token_returns_none_without_credentials():
    ws = MagicMock()
    ws.query_params.get.return_value = None
    ws.cookies.get.return_value = None

    assert extract_websocket_session_token(ws) is None