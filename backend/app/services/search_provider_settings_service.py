import os

from app.database import db_connection
from app.models import (
    SearchProviderListResponse,
    SearchProviderName,
    SearchProviderSettingsUpdate,
    SearchProviderSummary,
)
from app.search_providers import SEARCH_PROVIDERS, get_search_provider
from app.services.credential_crypto import decrypt_api_key, encrypt_api_key


def _summary(provider: SearchProviderName, has_stored_key: bool) -> SearchProviderSummary:
    definition = get_search_provider(provider)
    return SearchProviderSummary(
        provider=provider,
        label=definition.label,
        description=definition.description,
        docs_url=definition.docs_url,
        has_api_key=has_stored_key or bool(os.environ.get(definition.env_key)),
        has_user_api_key=has_stored_key,
    )


def list_search_provider_settings(user_id: str) -> SearchProviderListResponse:
    with db_connection() as conn:
        configured = {
            row["provider"]
            for row in conn.execute(
                "SELECT provider FROM user_search_provider_settings WHERE user_id = ? AND api_key_encrypted IS NOT NULL",
                (user_id,),
            ).fetchall()
        }
    return SearchProviderListResponse(
        providers=[_summary(provider, provider in configured) for provider in SEARCH_PROVIDERS]
    )


def update_search_provider_settings(user_id: str, data: SearchProviderSettingsUpdate) -> SearchProviderSummary:
    encrypted_key = encrypt_api_key(data.api_key) if data.api_key else None
    with db_connection() as conn:
        existing = conn.execute(
            "SELECT api_key_encrypted FROM user_search_provider_settings WHERE user_id = ? AND provider = ?",
            (user_id, data.provider),
        ).fetchone()
        key_value = encrypted_key or (existing["api_key_encrypted"] if existing else None)
        conn.execute(
            """
            INSERT INTO user_search_provider_settings (user_id, provider, api_key_encrypted)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, provider) DO UPDATE SET
                api_key_encrypted = excluded.api_key_encrypted,
                updated_at = datetime('now')
            """,
            (user_id, data.provider, key_value),
        )
        conn.commit()
    return _summary(data.provider, bool(key_value))


def clear_search_provider_key(user_id: str, provider: SearchProviderName) -> SearchProviderSummary:
    with db_connection() as conn:
        conn.execute(
            "DELETE FROM user_search_provider_settings WHERE user_id = ? AND provider = ?",
            (user_id, provider),
        )
        conn.commit()
    return _summary(provider, False)


def resolve_search_api_key(user_id: str, provider: SearchProviderName) -> str | None:
    with db_connection() as conn:
        row = conn.execute(
            "SELECT api_key_encrypted FROM user_search_provider_settings WHERE user_id = ? AND provider = ?",
            (user_id, provider),
        ).fetchone()
    user_key = decrypt_api_key(row["api_key_encrypted"] if row else None)
    if user_key:
        return user_key
    return os.environ.get(get_search_provider(provider).env_key)
