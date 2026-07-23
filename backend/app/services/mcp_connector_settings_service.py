import os

from app.database import db_connection
from app.mcp_connectors import MCP_CONNECTORS, get_mcp_connector
from app.models import (
    DefaultMcpKey,
    McpConnectorListResponse,
    McpConnectorSettingsUpdate,
    McpConnectorSummary,
)
from app.services.credential_crypto import decrypt_api_key, encrypt_api_key


def _summary(key: DefaultMcpKey, has_stored_key: bool) -> McpConnectorSummary:
    definition = get_mcp_connector(key)
    return McpConnectorSummary(
        key=key,
        label=definition.label,
        description=definition.description,
        docs_url=definition.docs_url,
        connection_url=definition.connection_url,
        default_url=definition.default_url,
        has_api_key=has_stored_key or bool(os.environ.get(definition.env_key)),
        has_user_api_key=has_stored_key,
        enabled_by_default=definition.enabled_by_default,
    )


def list_mcp_connector_settings(user_id: str) -> McpConnectorListResponse:
    with db_connection() as conn:
        configured = {
            row["connector_key"]
            for row in conn.execute(
                "SELECT connector_key FROM user_mcp_connector_settings WHERE user_id = ? AND api_key_encrypted IS NOT NULL",
                (user_id,),
            ).fetchall()
        }
    return McpConnectorListResponse(
        connectors=[_summary(key, key in configured) for key in MCP_CONNECTORS]
    )


def update_mcp_connector_settings(user_id: str, data: McpConnectorSettingsUpdate) -> McpConnectorSummary:
    encrypted_key = encrypt_api_key(data.api_key) if data.api_key else None
    with db_connection() as conn:
        existing = conn.execute(
            "SELECT api_key_encrypted FROM user_mcp_connector_settings WHERE user_id = ? AND connector_key = ?",
            (user_id, data.key),
        ).fetchone()
        key_value = encrypted_key or (existing["api_key_encrypted"] if existing else None)
        conn.execute(
            """
            INSERT INTO user_mcp_connector_settings (user_id, connector_key, api_key_encrypted)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, connector_key) DO UPDATE SET
                api_key_encrypted = excluded.api_key_encrypted,
                updated_at = datetime('now')
            """,
            (user_id, data.key, key_value),
        )
        conn.commit()
    return _summary(data.key, bool(key_value))


def clear_mcp_connector_key(user_id: str, key: DefaultMcpKey) -> McpConnectorSummary:
    with db_connection() as conn:
        conn.execute(
            "DELETE FROM user_mcp_connector_settings WHERE user_id = ? AND connector_key = ?",
            (user_id, key),
        )
        conn.commit()
    return _summary(key, False)


def resolve_mcp_api_key(user_id: str | None, key: DefaultMcpKey) -> str | None:
    """Resolve an MCP credential from the user's encrypted UI settings.

    Env vars are only a local-dev fallback for unauthenticated or unconfigured
    accounts. Production users store keys through the Connectors UI.
    """
    if user_id:
        with db_connection() as conn:
            row = conn.execute(
                "SELECT api_key_encrypted FROM user_mcp_connector_settings WHERE user_id = ? AND connector_key = ?",
                (user_id, key),
            ).fetchone()
        user_key = decrypt_api_key(row["api_key_encrypted"] if row else None)
        if user_key:
            return user_key
    return os.environ.get(get_mcp_connector(key).env_key)
