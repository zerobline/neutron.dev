from app.database import db_connection
from app.models import McpConnectorSettingsUpdate, UserCreate
from app.services import auth_service, mcp_connector_settings_service


def make_user():
    return auth_service.create_user(UserCreate(email="mcp-connector@example.com", password="password123"))


def test_mcp_connector_settings_encrypt_preserve_resolve_and_clear(temp_db, monkeypatch):
    for env_key in ("GITHUB_TOKEN", "LINEAR_API_KEY"):
        monkeypatch.delenv(env_key, raising=False)
    user = make_user()

    initial = mcp_connector_settings_service.list_mcp_connector_settings(user.id)
    assert [connector.key for connector in initial.connectors] == ["github", "linear"]
    assert all(connector.has_api_key is False for connector in initial.connectors)
    assert all(connector.has_user_api_key is False for connector in initial.connectors)
    assert all(connector.enabled_by_default is True for connector in initial.connectors)

    empty = mcp_connector_settings_service.update_mcp_connector_settings(
        user.id,
        McpConnectorSettingsUpdate(key="linear", api_key=None),
    )
    assert empty.has_api_key is False

    saved = mcp_connector_settings_service.update_mcp_connector_settings(
        user.id,
        McpConnectorSettingsUpdate(key="github", api_key="ghp-secret"),
    )
    assert saved.has_api_key is True
    assert saved.has_user_api_key is True
    assert mcp_connector_settings_service.resolve_mcp_api_key(user.id, "github") == "ghp-secret"

    with db_connection() as conn:
        row = conn.execute(
            "SELECT api_key_encrypted FROM user_mcp_connector_settings WHERE user_id = ? AND connector_key = ?",
            (user.id, "github"),
        ).fetchone()
    assert row is not None
    assert row["api_key_encrypted"] != "ghp-secret"
    assert "ghp-secret" not in row["api_key_encrypted"]

    preserved = mcp_connector_settings_service.update_mcp_connector_settings(
        user.id,
        McpConnectorSettingsUpdate(key="github", api_key=""),
    )
    assert preserved.has_api_key is True
    assert mcp_connector_settings_service.resolve_mcp_api_key(user.id, "github") == "ghp-secret"

    cleared = mcp_connector_settings_service.clear_mcp_connector_key(user.id, "github")
    assert cleared.has_api_key is False
    assert cleared.has_user_api_key is False
    assert mcp_connector_settings_service.resolve_mcp_api_key(user.id, "github") is None


def test_mcp_connector_settings_use_environment_fallback(temp_db, monkeypatch):
    user = make_user()
    monkeypatch.setenv("LINEAR_API_KEY", "server-linear-key")

    listed = mcp_connector_settings_service.list_mcp_connector_settings(user.id)
    linear = next(connector for connector in listed.connectors if connector.key == "linear")
    assert linear.has_api_key is True
    assert linear.has_user_api_key is False
    assert mcp_connector_settings_service.resolve_mcp_api_key(user.id, "linear") == "server-linear-key"
    # Unauthenticated / missing user_id path still allows local-dev env fallback.
    assert mcp_connector_settings_service.resolve_mcp_api_key(None, "linear") == "server-linear-key"

    cleared = mcp_connector_settings_service.clear_mcp_connector_key(user.id, "linear")
    assert cleared.has_api_key is True
    assert cleared.has_user_api_key is False
