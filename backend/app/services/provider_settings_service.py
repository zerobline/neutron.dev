from app.config import settings
from app.database import db_connection
from app.models import ProviderListResponse, ProviderName, ProviderSettingsUpdate, ProviderSummary
from app.providers import PROVIDERS, get_provider, prefixed_model, provider_model
from app.services.credential_crypto import decrypt_api_key, encrypt_api_key
from app.services import xai_oauth_service


def _active_provider(conn, user_id: str) -> ProviderName:
    row = conn.execute("SELECT active_provider FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
    if row:
        return row["active_provider"]

    # First-time authenticated user: derive active provider + model from global .env / settings
    # (instead of hardcoding "openai"). The .env key is NOT copied here; user must configure
    # their credentials via Settings UI for the DB-backed path used by authenticated builds.
    default_provider: ProviderName = settings.infer_provider()
    default_model = settings.default_model_for_provider(default_provider)
    default_base_url = settings.default_base_url_for_provider(default_provider)

    conn.execute(
        "INSERT INTO user_settings (user_id, active_provider) VALUES (?, ?)",
        (user_id, default_provider),
    )
    # Seed a skeleton row for the chosen provider so that list/get and summaries report
    # the globally-configured model (not the provider's hardcoded default_model).
    # No api_key is seeded from .env.
    conn.execute(
        """
        INSERT INTO user_provider_settings (user_id, provider, model, base_url, api_key_encrypted)
        VALUES (?, ?, ?, ?, NULL)
        ON CONFLICT(user_id, provider) DO NOTHING
        """,
        (user_id, default_provider, default_model, default_base_url),
    )
    conn.commit()
    return default_provider


def _has_provider_credentials(provider: ProviderName, row) -> bool:
    if provider == "xai-oauth":
        return bool(row and row["oauth_tokens_encrypted"])
    if row and row["api_key_encrypted"]:
        return True
    return settings.allow_shared_provider_keys and bool(settings.get_api_key_for_provider(provider))


def _summary_from_row(provider: ProviderName, active_provider: ProviderName, row) -> ProviderSummary:
    definition = get_provider(provider)
    model = row["model"] if row and row["model"] else definition.default_model
    base_url = row["base_url"] if row and row["base_url"] is not None else definition.default_base_url
    connected = _has_provider_credentials(provider, row)
    return ProviderSummary(
        provider=provider,
        label=definition.label,
        model=model,
        base_url=base_url,
        has_api_key=connected,
        effective_model=prefixed_model(provider, model),
        is_active=provider == active_provider,
        requires_base_url=definition.requires_base_url,
        requires_api_key=definition.requires_api_key,
        auth_method=definition.auth_method,
        is_connected=connected,
    )


def list_provider_settings(user_id: str) -> ProviderListResponse:
    with db_connection() as conn:
        active_provider = _active_provider(conn, user_id)
        rows = {
            row["provider"]: row
            for row in conn.execute("SELECT * FROM user_provider_settings WHERE user_id = ?", (user_id,)).fetchall()
        }
    return ProviderListResponse(
        providers=[_summary_from_row(provider, active_provider, rows.get(provider)) for provider in PROVIDERS],
        active_provider=active_provider,
    )


def get_active_provider_settings(user_id: str) -> ProviderSummary:
    with db_connection() as conn:
        active_provider = _active_provider(conn, user_id)
        row = conn.execute(
            "SELECT * FROM user_provider_settings WHERE user_id = ? AND provider = ?",
            (user_id, active_provider),
        ).fetchone()
    return _summary_from_row(active_provider, active_provider, row)


def get_provider_settings(user_id: str, provider: ProviderName) -> ProviderSummary:
    with db_connection() as conn:
        active_provider = _active_provider(conn, user_id)
        row = conn.execute(
            "SELECT * FROM user_provider_settings WHERE user_id = ? AND provider = ?",
            (user_id, provider),
        ).fetchone()
    return _summary_from_row(provider, active_provider, row)


def update_provider_settings(user_id: str, data: ProviderSettingsUpdate, activate: bool = True) -> ProviderSummary:
    definition = get_provider(data.provider)
    base_url = data.base_url if data.base_url is not None else definition.default_base_url
    if definition.requires_base_url and not base_url:
        raise ValueError(f"{definition.label} requires a base URL.")
    encrypted_key = encrypt_api_key(data.api_key) if data.api_key else None
    with db_connection() as conn:
        existing = conn.execute(
            "SELECT api_key_encrypted FROM user_provider_settings WHERE user_id = ? AND provider = ?",
            (user_id, data.provider),
        ).fetchone()
        key_value = None if data.clear_api_key else (encrypted_key or (existing["api_key_encrypted"] if existing else None))
        conn.execute(
            """
            INSERT INTO user_provider_settings (user_id, provider, model, base_url, api_key_encrypted)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, provider) DO UPDATE SET
                model = excluded.model,
                base_url = excluded.base_url,
                api_key_encrypted = excluded.api_key_encrypted,
                updated_at = datetime('now')
            """,
            (user_id, data.provider, data.model, base_url, key_value),
        )
        if activate:
            conn.execute(
                """
                INSERT INTO user_settings (user_id, active_provider) VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET active_provider = excluded.active_provider, updated_at = datetime('now')
                """,
                (user_id, data.provider),
            )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM user_provider_settings WHERE user_id = ? AND provider = ?",
            (user_id, data.provider),
        ).fetchone()
        active_provider = _active_provider(conn, user_id)
    return _summary_from_row(data.provider, active_provider, row)


def activate_provider(user_id: str, provider: ProviderName) -> ProviderSummary:
    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO user_settings (user_id, active_provider) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET active_provider = excluded.active_provider, updated_at = datetime('now')
            """,
            (user_id, provider),
        )
        conn.commit()
    return get_active_provider_settings(user_id)


def clear_provider_key(user_id: str, provider: ProviderName) -> ProviderSummary:
    definition = get_provider(provider)
    if provider == "xai-oauth":
        xai_oauth_service.clear_oauth_tokens(user_id)
        return get_provider_settings(user_id, provider)
    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO user_provider_settings (user_id, provider, model, base_url, api_key_encrypted)
            VALUES (?, ?, ?, ?, NULL)
            ON CONFLICT(user_id, provider) DO UPDATE SET api_key_encrypted = NULL, updated_at = datetime('now')
            """,
            (user_id, provider, definition.default_model, definition.default_base_url),
        )
        conn.commit()
    return activate_provider(user_id, provider)


def provider_ready_for_build(user_id: str) -> tuple[bool, str]:
    summary = get_active_provider_settings(user_id)
    definition = get_provider(summary.provider)
    if definition.auth_method == "oauth":
        # Presence of an encrypted blob is not enough: refresh may fail or the
        # stored payload may be corrupt. Require a resolvable access token.
        try:
            token = xai_oauth_service.ensure_fresh_access_token(user_id)
        except Exception:
            return False, "Reconnect Grok OAuth in Settings → Cloud & AI before starting a build."
        if token:
            return True, ""
        return False, "Connect your AI provider in Settings → Cloud & AI before starting a build."
    if not definition.requires_api_key or summary.is_connected:
        return True, ""
    return False, f"Add your {definition.label} API key in Settings → Cloud & AI before starting a build."


def resolve_litellm_config(user_id: str) -> dict[str, str | None]:
    with db_connection() as conn:
        active_provider = _active_provider(conn, user_id)
        row = conn.execute(
            "SELECT * FROM user_provider_settings WHERE user_id = ? AND provider = ?",
            (user_id, active_provider),
        ).fetchone()
    definition = get_provider(active_provider)
    model = row["model"] if row and row["model"] else definition.default_model

    # Prefer per-user base_url/model (set via UI), fall back to global .env settings
    user_base = row["base_url"] if row and row["base_url"] is not None else None
    if user_base is not None:
        base_url = user_base
    else:
        base_url = settings.get_base_url_for_provider(active_provider) or definition.default_base_url

    if active_provider == "xai-oauth":
        api_key = xai_oauth_service.ensure_fresh_access_token(user_id)
    else:
        user_key = decrypt_api_key(row["api_key_encrypted"] if row else None)
        if user_key:
            api_key = user_key
        elif settings.allow_shared_provider_keys:
            api_key = settings.get_api_key_for_provider(active_provider)
        else:
            api_key = None
    return {
        "provider": active_provider,
        "model": prefixed_model(active_provider, model),
        "api_key": api_key,
        "base_url": base_url,
    }


def normalized_provider_model(provider: ProviderName, model: str) -> str:
    return provider_model(provider, model)
