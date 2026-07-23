import json
import time
from unittest.mock import patch

import pytest

from app.database import db_connection
from app.models import UserCreate
from app.services import auth_service, xai_oauth_service
from app.services.credential_crypto import encrypt_api_key


def make_user(email="xai-oauth@example.com"):
    return auth_service.create_user(UserCreate(email=email, password="password123"))


def test_tokens_round_trip_encryption():
    tokens = xai_oauth_service.OAuthTokens(
        access_token="access",
        refresh_token="refresh",
        expires_at=time.time() + 3600,
    )
    encrypted = xai_oauth_service._serialize_tokens(tokens)
    restored = xai_oauth_service._deserialize_tokens(encrypted)
    assert restored == tokens


def test_deserialize_tokens_handles_empty_values():
    assert xai_oauth_service._deserialize_tokens(None) is None
    assert xai_oauth_service._deserialize_tokens("") is None


def test_tokens_from_payload_requires_access_and_refresh():
    with pytest.raises(ValueError, match="access token"):
        xai_oauth_service._tokens_from_payload({})
    with pytest.raises(ValueError, match="refresh token"):
        xai_oauth_service._tokens_from_payload({"access_token": "a"})


def test_http_post_form_success_and_errors(monkeypatch):
    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def read(self):
            return json.dumps(self._payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(xai_oauth_service.request, "urlopen", lambda *_args, **_kwargs: FakeResponse({"ok": True}))
    assert xai_oauth_service._http_post_form("https://example.com", {"a": "b"}) == {"ok": True}

    import io
    from urllib import error

    def raise_http_error(*_args, **_kwargs):
        raise error.HTTPError("https://example.com", 400, "bad", {}, io.BytesIO(b"bad request"))

    monkeypatch.setattr(xai_oauth_service.request, "urlopen", raise_http_error)
    with pytest.raises(ValueError, match="400"):
        xai_oauth_service._http_post_form("https://example.com", {"a": "b"})

    def raise_url_error(*_args, **_kwargs):
        raise error.URLError("offline")

    monkeypatch.setattr(xai_oauth_service.request, "urlopen", raise_url_error)
    with pytest.raises(ValueError, match="offline"):
        xai_oauth_service._http_post_form("https://example.com", {"a": "b"})

    def raise_invalid_json(*_args, **_kwargs):
        class BadResponse:
            def read(self):
                return b"not-json"

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        return BadResponse()

    monkeypatch.setattr(xai_oauth_service.request, "urlopen", lambda *_args, **_kwargs: raise_invalid_json())
    with pytest.raises(ValueError, match="valid JSON"):
        xai_oauth_service._http_post_form("https://example.com", {"a": "b"})


def test_start_device_flow_stores_session(temp_db, monkeypatch):
    user = make_user()
    monkeypatch.setattr(
        xai_oauth_service,
        "_http_post_form",
        lambda *_args, **_kwargs: {
            "device_code": "device-123",
            "user_code": "ABCD-1234",
            "verification_uri": "https://auth.x.ai/device",
            "expires_in": 600,
            "interval": 5,
        },
    )

    result = xai_oauth_service.start_device_flow(user.id)

    assert result["user_code"] == "ABCD-1234"
    assert result["verification_uri"] == "https://auth.x.ai/device"
    with db_connection() as conn:
        row = conn.execute("SELECT device_code FROM oauth_device_sessions WHERE id = ?", (result["session_id"],)).fetchone()
    assert row["device_code"] == "device-123"


def test_start_device_flow_rejects_incomplete_response(temp_db):
    user = make_user()
    with patch.object(xai_oauth_service, "_http_post_form", return_value={"device_code": "only"}):
        with pytest.raises(ValueError, match="incomplete"):
            xai_oauth_service.start_device_flow(user.id)


def test_poll_device_flow_pending_complete_and_terminal_states(temp_db, monkeypatch):
    user = make_user()

    def device_then_pending(url, _data):
        if "device/code" in url:
            return {
                "device_code": "device-123",
                "user_code": "ABCD-1234",
                "verification_uri": "https://auth.x.ai/device",
                "expires_in": 600,
                "interval": 5,
            }
        raise ValueError('400 {"error":"authorization_pending"}')

    monkeypatch.setattr(xai_oauth_service, "_http_post_form", device_then_pending)
    started = xai_oauth_service.start_device_flow(user.id)
    pending = xai_oauth_service.poll_device_flow(user.id, started["session_id"])
    assert pending == {"status": "pending", "interval": 5}

    monkeypatch.setattr(
        xai_oauth_service,
        "_http_post_form",
        lambda *_args, **_kwargs: {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "expires_in": 3600,
        },
    )
    complete = xai_oauth_service.poll_device_flow(user.id, started["session_id"])
    assert complete == {"status": "complete", "connected": True}
    assert xai_oauth_service.get_oauth_tokens(user.id) is not None
    with db_connection() as conn:
        active = conn.execute(
            "SELECT active_provider FROM user_settings WHERE user_id = ?",
            (user.id,),
        ).fetchone()
    assert active is not None
    assert active["active_provider"] == "xai-oauth"

    missing = xai_oauth_service.poll_device_flow(user.id, started["session_id"])
    assert missing == {"status": "expired"}


def test_poll_device_flow_denied_and_slow_down(temp_db, monkeypatch):
    user = make_user()
    monkeypatch.setattr(
        xai_oauth_service,
        "_http_post_form",
        lambda url, data: {
            "device_code": "device-123",
            "user_code": "ABCD-1234",
            "verification_uri": "https://auth.x.ai/device",
            "expires_in": 600,
            "interval": 4,
        },
    )
    started = xai_oauth_service.start_device_flow(user.id)

    monkeypatch.setattr(
        xai_oauth_service,
        "_http_post_form",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError('400 {"error":"slow_down"}')),
    )
    assert xai_oauth_service.poll_device_flow(user.id, started["session_id"]) == {"status": "pending", "interval": 9}

    monkeypatch.setattr(
        xai_oauth_service,
        "_http_post_form",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError('400 {"error":"access_denied"}')),
    )
    assert xai_oauth_service.poll_device_flow(user.id, started["session_id"]) == {"status": "denied"}


def test_refresh_and_ensure_fresh_access_token(temp_db, monkeypatch):
    user = make_user()
    tokens = xai_oauth_service.OAuthTokens(
        access_token="old-access",
        refresh_token="refresh-token",
        expires_at=time.time() - 10,
    )
    xai_oauth_service.store_oauth_tokens(user.id, tokens)

    monkeypatch.setattr(
        xai_oauth_service,
        "_http_post_form",
        lambda *_args, **_kwargs: {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_in": 3600,
        },
    )
    refreshed = xai_oauth_service.refresh_oauth_tokens(tokens)
    assert refreshed.access_token == "new-access"
    assert xai_oauth_service.ensure_fresh_access_token(user.id) == "new-access"


def test_ensure_fresh_access_token_returns_cached_token(temp_db):
    user = make_user()
    tokens = xai_oauth_service.OAuthTokens(
        access_token="fresh-access",
        refresh_token="refresh-token",
        expires_at=time.time() + 3600,
    )
    xai_oauth_service.store_oauth_tokens(user.id, tokens)
    assert xai_oauth_service.ensure_fresh_access_token(user.id) == "fresh-access"


def test_clear_oauth_tokens(temp_db):
    user = make_user()
    tokens = xai_oauth_service.OAuthTokens(
        access_token="access",
        refresh_token="refresh",
        expires_at=time.time() + 3600,
    )
    xai_oauth_service.store_oauth_tokens(user.id, tokens)
    xai_oauth_service.clear_oauth_tokens(user.id)
    assert xai_oauth_service.get_oauth_tokens(user.id) is None


def test_deserialize_tokens_rejects_invalid_payload(monkeypatch):
    invalid = encrypt_api_key(json.dumps({"access_token": "only"}))
    assert xai_oauth_service._deserialize_tokens(invalid) is None
    monkeypatch.setattr("app.services.xai_oauth_service.decrypt_api_key", lambda _value: "")
    assert xai_oauth_service._deserialize_tokens("encrypted") is None


def test_get_oauth_tokens_without_row(temp_db):
    user = make_user()
    assert xai_oauth_service.get_oauth_tokens(user.id) is None


def test_ensure_fresh_access_token_without_tokens(temp_db):
    user = make_user()
    assert xai_oauth_service.ensure_fresh_access_token(user.id) is None


def test_poll_device_flow_expired_session(temp_db, monkeypatch):
    user = make_user()
    monkeypatch.setattr(
        xai_oauth_service,
        "_http_post_form",
        lambda *_args, **_kwargs: {
            "device_code": "device-123",
            "user_code": "ABCD-1234",
            "verification_uri": "https://auth.x.ai/device",
            "expires_in": 1,
            "interval": 5,
        },
    )
    started = xai_oauth_service.start_device_flow(user.id)
    time.sleep(1.1)
    assert xai_oauth_service.poll_device_flow(user.id, started["session_id"]) == {"status": "expired"}


def test_poll_device_flow_error_json_parse_fallback(temp_db, monkeypatch):
    user = make_user()
    monkeypatch.setattr(
        xai_oauth_service,
        "_http_post_form",
        lambda url, data: {
            "device_code": "device-123",
            "user_code": "ABCD-1234",
            "verification_uri": "https://auth.x.ai/device",
            "expires_in": 600,
            "interval": 5,
        },
    )
    started = xai_oauth_service.start_device_flow(user.id)
    monkeypatch.setattr(
        xai_oauth_service,
        "_http_post_form",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError('400 {not valid json')),
    )
    with pytest.raises(ValueError, match="not valid json"):
        xai_oauth_service.poll_device_flow(user.id, started["session_id"])


def test_poll_device_flow_invalid_grant_and_unhandled_error(temp_db, monkeypatch):
    user = make_user()
    monkeypatch.setattr(
        xai_oauth_service,
        "_http_post_form",
        lambda url, data: {
            "device_code": "device-123",
            "user_code": "ABCD-1234",
            "verification_uri": "https://auth.x.ai/device",
            "expires_in": 600,
            "interval": 5,
        },
    )
    started = xai_oauth_service.start_device_flow(user.id)

    monkeypatch.setattr(
        xai_oauth_service,
        "_http_post_form",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError('400 {"error":"invalid_grant"}')),
    )
    assert xai_oauth_service.poll_device_flow(user.id, started["session_id"]) == {"status": "expired"}

    def start_then_fail(url, _data):
        if "device/code" in url:
            return {
                "device_code": "device-456",
                "user_code": "WXYZ-5678",
                "verification_uri": "https://auth.x.ai/device",
                "expires_in": 600,
                "interval": 5,
            }
        raise ValueError("poll failed")

    monkeypatch.setattr(xai_oauth_service, "_http_post_form", start_then_fail)
    started_again = xai_oauth_service.start_device_flow(user.id)
    with pytest.raises(ValueError, match="poll failed"):
        xai_oauth_service.poll_device_flow(user.id, started_again["session_id"])