import json
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request

from app.database import db_connection
from app.services.credential_crypto import decrypt_api_key, encrypt_api_key

XAI_OAUTH_CLIENT_ID = "b1a00492-073a-47ea-816f-4c329264a828"
XAI_OAUTH_SCOPE = "openid profile email offline_access grok-cli:access api:access"
XAI_DEVICE_ENDPOINT = "https://auth.x.ai/oauth2/device/code"
XAI_TOKEN_ENDPOINT = "https://auth.x.ai/oauth2/token"
REFRESH_SKEW_SECONDS = 120


@dataclass(frozen=True)
class OAuthTokens:
    access_token: str
    refresh_token: str
    expires_at: float
    token_endpoint: str = XAI_TOKEN_ENDPOINT


def _http_post_form(url: str, data: dict[str, str]) -> dict[str, Any]:
    body = parse.urlencode(data).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=30) as response:
            payload = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ValueError(f"xAI OAuth request failed: {exc.code} {detail}") from exc
    except error.URLError as exc:
        raise ValueError(f"xAI OAuth request failed: {exc.reason}") from exc

    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError("xAI OAuth response was not valid JSON.") from exc


def _serialize_tokens(tokens: OAuthTokens) -> str:
    return encrypt_api_key(
        json.dumps(
            {
                "access_token": tokens.access_token,
                "refresh_token": tokens.refresh_token,
                "expires_at": tokens.expires_at,
                "token_endpoint": tokens.token_endpoint,
            }
        )
    )


def _deserialize_tokens(value: str | None) -> OAuthTokens | None:
    if not value:
        return None
    raw = decrypt_api_key(value)
    if not raw:
        return None
    data = json.loads(raw)
    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")
    expires_at = data.get("expires_at")
    if not access_token or not refresh_token or expires_at is None:
        return None
    token_endpoint = data.get("token_endpoint") or XAI_TOKEN_ENDPOINT
    return OAuthTokens(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=float(expires_at),
        token_endpoint=token_endpoint,
    )


def _tokens_from_payload(payload: dict[str, Any], fallback_refresh: str = "") -> OAuthTokens:
    access_token = payload.get("access_token")
    refresh_token = payload.get("refresh_token") or fallback_refresh
    if not access_token:
        raise ValueError("xAI token response did not include an access token.")
    if not refresh_token:
        raise ValueError("xAI token response did not include a refresh token.")
    expires_in = int(payload.get("expires_in") or 3600)
    return OAuthTokens(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=time.time() + expires_in - REFRESH_SKEW_SECONDS,
        token_endpoint=XAI_TOKEN_ENDPOINT,
    )


def store_oauth_tokens(user_id: str, tokens: OAuthTokens) -> None:
    encrypted = _serialize_tokens(tokens)
    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO user_provider_settings (user_id, provider, model, base_url, api_key_encrypted, oauth_tokens_encrypted)
            VALUES (?, 'xai-oauth', 'grok-4.20-reasoning', 'https://api.x.ai/v1', NULL, ?)
            ON CONFLICT(user_id, provider) DO UPDATE SET
                oauth_tokens_encrypted = excluded.oauth_tokens_encrypted,
                api_key_encrypted = NULL,
                updated_at = datetime('now')
            """,
            (user_id, encrypted),
        )
        # Completing OAuth means the user intends to build with Grok. Activate it
        # so resolve_litellm_config does not keep using a previous provider that
        # has no credentials and later fails with unauthenticated:no-credentials.
        conn.execute(
            """
            INSERT INTO user_settings (user_id, active_provider) VALUES (?, 'xai-oauth')
            ON CONFLICT(user_id) DO UPDATE SET
                active_provider = excluded.active_provider,
                updated_at = datetime('now')
            """,
            (user_id,),
        )
        conn.commit()


def clear_oauth_tokens(user_id: str) -> None:
    with db_connection() as conn:
        conn.execute(
            """
            UPDATE user_provider_settings
            SET oauth_tokens_encrypted = NULL, updated_at = datetime('now')
            WHERE user_id = ? AND provider = 'xai-oauth'
            """,
            (user_id,),
        )
        conn.commit()


def get_oauth_tokens(user_id: str) -> OAuthTokens | None:
    with db_connection() as conn:
        row = conn.execute(
            "SELECT oauth_tokens_encrypted FROM user_provider_settings WHERE user_id = ? AND provider = 'xai-oauth'",
            (user_id,),
        ).fetchone()
    if not row:
        return None
    return _deserialize_tokens(row["oauth_tokens_encrypted"])


def refresh_oauth_tokens(tokens: OAuthTokens) -> OAuthTokens:
    payload = _http_post_form(
        tokens.token_endpoint,
        {
            "grant_type": "refresh_token",
            "refresh_token": tokens.refresh_token,
            "client_id": XAI_OAUTH_CLIENT_ID,
        },
    )
    return _tokens_from_payload(payload, fallback_refresh=tokens.refresh_token)


def ensure_fresh_access_token(user_id: str) -> str | None:
    tokens = get_oauth_tokens(user_id)
    if tokens is None:
        return None
    if tokens.expires_at > time.time():
        return tokens.access_token
    refreshed = refresh_oauth_tokens(tokens)
    store_oauth_tokens(user_id, refreshed)
    return refreshed.access_token


def start_device_flow(user_id: str) -> dict[str, str | int]:
    payload = _http_post_form(
        XAI_DEVICE_ENDPOINT,
        {
            "client_id": XAI_OAUTH_CLIENT_ID,
            "scope": XAI_OAUTH_SCOPE,
        },
    )
    device_code = payload.get("device_code")
    user_code = payload.get("user_code")
    verification_uri = payload.get("verification_uri") or payload.get("verification_uri_complete")
    expires_in = int(payload.get("expires_in") or 600)
    interval = int(payload.get("interval") or 5)
    if not device_code or not user_code or not verification_uri:
        raise ValueError("xAI device authorization response was incomplete.")

    session_id = str(uuid.uuid4())
    with db_connection() as conn:
        conn.execute("DELETE FROM oauth_device_sessions WHERE user_id = ?", (user_id,))
        conn.execute(
            """
            INSERT INTO oauth_device_sessions (id, user_id, device_code, expires_at, interval_seconds)
            VALUES (?, ?, ?, datetime('now', ?), ?)
            """,
            (session_id, user_id, device_code, f"+{expires_in} seconds", interval),
        )
        conn.commit()

    return {
        "session_id": session_id,
        "verification_uri": verification_uri,
        "user_code": user_code,
        "expires_in": expires_in,
        "interval": interval,
    }


def _get_device_session(user_id: str, session_id: str):
    with db_connection() as conn:
        return conn.execute(
            """
            SELECT id, device_code, expires_at, interval_seconds
            FROM oauth_device_sessions
            WHERE id = ? AND user_id = ?
            """,
            (session_id, user_id),
        ).fetchone()


def _delete_device_session(session_id: str) -> None:
    with db_connection() as conn:
        conn.execute("DELETE FROM oauth_device_sessions WHERE id = ?", (session_id,))
        conn.commit()


def poll_device_flow(user_id: str, session_id: str) -> dict[str, str | bool]:
    session = _get_device_session(user_id, session_id)
    if session is None:
        return {"status": "expired"}

    with db_connection() as conn:
        expired = conn.execute(
            "SELECT 1 FROM oauth_device_sessions WHERE id = ? AND expires_at <= datetime('now')",
            (session_id,),
        ).fetchone()
    if expired:
        _delete_device_session(session_id)
        return {"status": "expired"}

    try:
        payload = _http_post_form(
            XAI_TOKEN_ENDPOINT,
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": session["device_code"],
                "client_id": XAI_OAUTH_CLIENT_ID,
            },
        )
    except ValueError as exc:
        message = str(exc)
        error_code = message
        if "{" in message:
            try:
                payload = json.loads(message[message.index("{") :])
                error_code = str(payload.get("error") or message)
            except (json.JSONDecodeError, ValueError):
                error_code = message
        if error_code == "authorization_pending":
            return {"status": "pending", "interval": session["interval_seconds"]}
        if error_code == "slow_down":
            return {"status": "pending", "interval": session["interval_seconds"] + 5}
        if error_code == "access_denied":
            _delete_device_session(session_id)
            return {"status": "denied"}
        if error_code in {"expired_token", "invalid_grant"}:
            _delete_device_session(session_id)
            return {"status": "expired"}
        raise

    tokens = _tokens_from_payload(payload)
    store_oauth_tokens(user_id, tokens)
    _delete_device_session(session_id)
    return {"status": "complete", "connected": True}