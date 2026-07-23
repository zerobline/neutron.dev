from unittest.mock import patch

from app.models import UserCreate
from app.services import auth_service


def register_user(client, email="oauth@example.com"):
    response = client.post("/api/auth/register", json={"email": email, "password": "password123"})
    assert response.status_code == 201
    return response.json()


def test_xai_oauth_requires_auth(client):
    assert client.post("/api/oauth/xai/device").status_code == 401
    assert client.post("/api/oauth/xai/poll", json={"session_id": "abc"}).status_code == 401
    assert client.delete("/api/oauth/xai").status_code == 401


def test_xai_oauth_device_poll_and_disconnect(client):
    register_user(client)

    with patch(
        "app.api.routes.oauth.xai_oauth_service.start_device_flow",
        return_value={
            "session_id": "session-1",
            "verification_uri": "https://auth.x.ai/device",
            "user_code": "ABCD-1234",
            "expires_in": 600,
            "interval": 5,
        },
    ):
        start = client.post("/api/oauth/xai/device")
    assert start.status_code == 200
    assert start.json()["user_code"] == "ABCD-1234"

    with patch(
        "app.api.routes.oauth.xai_oauth_service.poll_device_flow",
        return_value={"status": "pending", "interval": 5},
    ):
        poll = client.post("/api/oauth/xai/poll", json={"session_id": "session-1"})
    assert poll.status_code == 200
    assert poll.json()["status"] == "pending"

    with patch("app.api.routes.oauth.xai_oauth_service.clear_oauth_tokens") as clear_mock:
        with patch(
            "app.api.routes.oauth.provider_settings_service.get_provider_settings",
            return_value={
                "provider": "xai-oauth",
                "label": "Grok OAuth (SuperGrok)",
                "model": "grok-4.5",
                "base_url": "https://api.x.ai/v1",
                "has_api_key": False,
                "effective_model": "xai/grok-4.5",
                "is_active": False,
                "requires_base_url": False,
                "requires_api_key": False,
                "auth_method": "oauth",
                "is_connected": False,
            },
        ):
            disconnect = client.delete("/api/oauth/xai")
    assert disconnect.status_code == 200
    clear_mock.assert_called_once()


def test_xai_oauth_start_value_error(client):
    register_user(client)
    with patch(
        "app.api.routes.oauth.xai_oauth_service.start_device_flow",
        side_effect=ValueError("device flow failed"),
    ):
        response = client.post("/api/oauth/xai/device")
    assert response.status_code == 400
    assert response.json()["detail"] == "device flow failed"


def test_xai_oauth_poll_value_error(client):
    register_user(client)
    with patch(
        "app.api.routes.oauth.xai_oauth_service.poll_device_flow",
        side_effect=ValueError("poll failed"),
    ):
        response = client.post("/api/oauth/xai/poll", json={"session_id": "session-1"})
    assert response.status_code == 400
    assert response.json()["detail"] == "poll failed"


def test_xai_oauth_integration_with_provider_settings(client, monkeypatch):
    register_user(client, email="oauth-integration@example.com")

    monkeypatch.setattr(
        "app.services.xai_oauth_service._http_post_form",
        lambda url, data: {
            "device_code": "device-123",
            "user_code": "ABCD-1234",
            "verification_uri": "https://auth.x.ai/device",
            "expires_in": 600,
            "interval": 5,
        }
        if "device/code" in url
        else {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "expires_in": 3600,
        },
    )

    started = client.post("/api/oauth/xai/device")
    assert started.status_code == 200
    session_id = started.json()["session_id"]

    polled = client.post("/api/oauth/xai/poll", json={"session_id": session_id})
    assert polled.status_code == 200
    assert polled.json()["status"] == "complete"

    update = client.put(
        "/api/settings/provider",
        json={"provider": "xai-oauth", "model": "grok-4.5", "base_url": "https://api.x.ai/v1"},
    )
    assert update.status_code == 200
    assert update.json()["has_api_key"] is True

    providers = client.get("/api/settings/providers")
    xai_oauth = next(item for item in providers.json()["providers"] if item["provider"] == "xai-oauth")
    assert xai_oauth["auth_method"] == "oauth"
    assert xai_oauth["is_connected"] is True