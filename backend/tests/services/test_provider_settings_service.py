import pytest
from cryptography.fernet import Fernet

from app.config import settings
from app.database import db_connection
from app.models import ProviderSettingsUpdate, UserCreate
from app.services import auth_service, provider_settings_service
from app.services.credential_crypto import decrypt_api_key, encrypt_api_key


def make_user(email="provider@example.com"):
    return auth_service.create_user(UserCreate(email=email, password="password123"))


def test_list_provider_settings_creates_default_user_settings(temp_db):
    # Force a known default via global config for deterministic test (otherwise derives from ollama->custom in test env)
    settings.llm_provider = "openai"
    settings.llm_model = "openai/gpt-4o"
    try:
        user = auth_service.create_user(UserCreate(email="new-default@example.com", password="password123"))
        with db_connection() as conn:
            conn.execute("DELETE FROM user_settings WHERE user_id = ?", (user.id,))
            conn.commit()

        result = provider_settings_service.list_provider_settings(user.id)

        assert result.active_provider == "openai"
        assert len(result.providers) == 12
        openai = next(provider for provider in result.providers if provider.provider == "openai")
        assert openai.is_active is True
        assert openai.label == "OpenAI"
        assert openai.model == "gpt-4o"
        assert openai.effective_model == "openai/gpt-4o"
    finally:
        settings.llm_provider = None
        settings.llm_model = "ollama/llama3.1"


def test_update_provider_settings_encrypts_preserves_clears_and_resolves_key(temp_db):
    user = make_user()

    saved = provider_settings_service.update_provider_settings(
        user.id,
        ProviderSettingsUpdate(provider="openai", model="gpt-4o", api_key="sk-secret"),
    )

    assert saved.has_api_key is True
    assert "sk-secret" not in saved.model
    config = provider_settings_service.resolve_litellm_config(user.id)
    assert config == {"provider": "openai", "model": "openai/gpt-4o", "api_key": "sk-secret", "base_url": None}

    preserved = provider_settings_service.update_provider_settings(
        user.id,
        ProviderSettingsUpdate(provider="openai", model="gpt-4o-mini", api_key=""),
    )
    assert preserved.has_api_key is True
    assert provider_settings_service.resolve_litellm_config(user.id)["api_key"] == "sk-secret"

    cleared = provider_settings_service.update_provider_settings(
        user.id,
        ProviderSettingsUpdate(provider="openai", model="gpt-4o-mini", clear_api_key=True),
    )
    assert cleared.has_api_key is False
    assert provider_settings_service.resolve_litellm_config(user.id)["api_key"] is None


def test_update_provider_settings_without_activation(temp_db):
    # Set desired global default *before* user creation, since create_user now seeds from current global
    settings.llm_provider = "openai"
    settings.llm_model = "openai/gpt-4o"
    user = make_user()

    saved = provider_settings_service.update_provider_settings(
        user.id,
        ProviderSettingsUpdate(provider="groq", model="llama-3.3-70b-versatile", api_key="groq-key"),
        activate=False,
    )

    assert saved.provider == "groq"
    assert provider_settings_service.get_active_provider_settings(user.id).provider == "openai"
    listed = provider_settings_service.list_provider_settings(user.id)
    groq = next(provider for provider in listed.providers if provider.provider == "groq")
    assert groq.is_active is False


def test_openai_compatible_requires_base_url_for_user(temp_db):
    user = make_user()

    with pytest.raises(ValueError, match="OpenAI-Compatible requires a base URL"):
        provider_settings_service.update_provider_settings(
            user.id,
            ProviderSettingsUpdate(provider="openai-compatible", model="local-model"),
        )


def test_openai_compatible_with_base_url_and_no_key(temp_db):
    user = make_user()

    saved = provider_settings_service.update_provider_settings(
        user.id,
        ProviderSettingsUpdate(provider="openai-compatible", model="local-model", base_url="http://localhost:1234/v1"),
    )

    assert saved.has_api_key is False
    assert saved.effective_model == "openai/local-model"
    assert provider_settings_service.resolve_litellm_config(user.id)["base_url"] == "http://localhost:1234/v1"


def test_activate_provider_and_clear_key_create_rows(temp_db):
    user = make_user()

    active = provider_settings_service.activate_provider(user.id, "nvidia")
    assert active.provider == "nvidia"
    assert active.effective_model == "nvidia/llama-3.3-nemotron-super-49b-v1.5"

    cleared = provider_settings_service.clear_provider_key(user.id, "nvidia")
    assert cleared.provider == "nvidia"
    assert cleared.has_api_key is False


def test_encryption_uses_configured_key(temp_db, monkeypatch):
    key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setattr("app.services.credential_crypto.settings.credential_encryption_key", key)

    encrypted = encrypt_api_key("secret")

    assert encrypted != "secret"
    assert decrypt_api_key(encrypted) == "secret"


def test_decrypt_empty_key_returns_none():
    assert decrypt_api_key(None) is None
    assert decrypt_api_key("") is None


def test_normalized_provider_model_strips_prefixes():
    assert provider_settings_service.normalized_provider_model("openai", "openai/gpt-4o") == "gpt-4o"
    assert provider_settings_service.normalized_provider_model("kimi", "openai/kimi-for-coding") == "kimi-for-coding"
    assert provider_settings_service.normalized_provider_model("custom", "vendor/model") == "vendor/model"


def test_xai_oauth_provider_settings_and_clear(temp_db, monkeypatch):
    user = make_user()
    monkeypatch.setattr(
        "app.services.xai_oauth_service.ensure_fresh_access_token",
        lambda _user_id: "oauth-access-token",
    )
    from app.services import xai_oauth_service

    xai_oauth_service.store_oauth_tokens(
        user.id,
        xai_oauth_service.OAuthTokens(
            access_token="oauth-access-token",
            refresh_token="refresh-token",
            expires_at=9999999999,
        ),
    )

    saved = provider_settings_service.update_provider_settings(
        user.id,
        ProviderSettingsUpdate(provider="xai-oauth", model="grok-4.5", base_url="https://api.x.ai/v1"),
    )
    assert saved.auth_method == "oauth"
    assert saved.is_connected is True
    assert saved.has_api_key is True

    config = provider_settings_service.resolve_litellm_config(user.id)
    assert config["provider"] == "xai-oauth"
    assert config["api_key"] == "oauth-access-token"
    assert config["base_url"] == "https://api.x.ai/v1"

    cleared = provider_settings_service.clear_provider_key(user.id, "xai-oauth")
    assert cleared.is_connected is False
    assert xai_oauth_service.get_oauth_tokens(user.id) is None
    provider_settings_service.activate_provider(user.id, "openai")
    assert provider_settings_service.resolve_litellm_config(user.id)["api_key"] is None


def test_provider_ready_for_build_requires_oauth_connection(temp_db):
    user = make_user("oauth-ready@example.com")
    provider_settings_service.activate_provider(user.id, "xai-oauth")
    ready, message = provider_settings_service.provider_ready_for_build(user.id)
    assert ready is False
    assert "Connect your AI provider" in message


def test_provider_ready_for_build_allows_connected_oauth(temp_db, monkeypatch):
    user = make_user("oauth-connected@example.com")
    monkeypatch.setattr(
        "app.services.provider_settings_service.xai_oauth_service.ensure_fresh_access_token",
        lambda _user_id: "oauth-access-token",
    )
    provider_settings_service.update_provider_settings(
        user.id,
        ProviderSettingsUpdate(provider="xai-oauth", model="grok-4.5", base_url="https://api.x.ai/v1"),
    )
    with db_connection() as conn:
        conn.execute(
            "UPDATE user_provider_settings SET oauth_tokens_encrypted = ? WHERE user_id = ? AND provider = ?",
            (encrypt_api_key("oauth-access-token"), user.id, "xai-oauth"),
        )
        conn.commit()
    ready, message = provider_settings_service.provider_ready_for_build(user.id)
    assert ready is True
    assert message == ""


def test_provider_ready_for_build_rejects_oauth_when_token_cannot_refresh(temp_db, monkeypatch):
    user = make_user("oauth-stale@example.com")
    provider_settings_service.update_provider_settings(
        user.id,
        ProviderSettingsUpdate(provider="xai-oauth", model="grok-4.5", base_url="https://api.x.ai/v1"),
    )
    with db_connection() as conn:
        conn.execute(
            "UPDATE user_provider_settings SET oauth_tokens_encrypted = ? WHERE user_id = ? AND provider = ?",
            (encrypt_api_key("stale-blob"), user.id, "xai-oauth"),
        )
        conn.commit()

    monkeypatch.setattr(
        "app.services.provider_settings_service.xai_oauth_service.ensure_fresh_access_token",
        lambda _user_id: None,
    )
    ready, message = provider_settings_service.provider_ready_for_build(user.id)
    assert ready is False
    assert "Connect your AI provider" in message

    def raise_refresh(_user_id):
        raise ValueError("refresh failed")

    monkeypatch.setattr(
        "app.services.provider_settings_service.xai_oauth_service.ensure_fresh_access_token",
        raise_refresh,
    )
    ready, message = provider_settings_service.provider_ready_for_build(user.id)
    assert ready is False
    assert "Reconnect Grok OAuth" in message


def test_provider_ready_for_build_requires_credentials(temp_db):
    # make_user now seeds default from global; use a key-requiring provider so test expectations hold
    settings.llm_provider = "openai"
    settings.llm_model = "openai/gpt-4o"
    user = make_user("ready@example.com")
    ready, message = provider_settings_service.provider_ready_for_build(user.id)
    assert ready is False
    assert "API key" in message

    provider_settings_service.update_provider_settings(
        user.id,
        ProviderSettingsUpdate(provider="openai", model="gpt-4o", api_key="sk-secret"),
    )
    ready, message = provider_settings_service.provider_ready_for_build(user.id)
    assert ready is True
    assert message == ""


def test_first_time_authenticated_user_derives_model_but_not_shared_key_by_default(temp_db):
    """Covers: new authenticated user inherits provider/model from .env/settings (not hardcoded openai).
    Credentials are NOT auto-seeded from global; user must configure in UI for auth builds.
    """
    original = {
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "kimi_api_key": settings.kimi_api_key,
        "kimi_base_url": settings.kimi_base_url,
        "allow_shared_provider_keys": settings.allow_shared_provider_keys,
    }
    try:
        settings.llm_provider = None
        settings.llm_model = "kimi/kimi-for-coding"
        settings.kimi_api_key = "sk-kimi-from-env"  # present globally but must not leak to user row
        settings.kimi_base_url = "https://api.kimi.com/coding/v1"
        settings.allow_shared_provider_keys = False

        user = make_user("first-time-kimi@example.com")

        # simulate first access with no persisted choice
        with db_connection() as conn:
            conn.execute("DELETE FROM user_settings WHERE user_id = ?", (user.id,))
            conn.execute("DELETE FROM user_provider_settings WHERE user_id = ?", (user.id,))
            conn.commit()

        # list triggers creation of default from global
        listed = provider_settings_service.list_provider_settings(user.id)
        assert listed.active_provider == "kimi"
        kimi_sum = next((p for p in listed.providers if p.provider == "kimi"), None)
        assert kimi_sum is not None
        assert kimi_sum.is_active is True
        assert kimi_sum.model == "kimi-for-coding"
        assert kimi_sum.base_url == "https://api.kimi.com/coding/v1"
        assert kimi_sum.has_api_key is False
        assert kimi_sum.effective_model == "openai/kimi-for-coding"

        # confirm the key was not copied into the DB row itself
        with db_connection() as conn:
            prow = conn.execute(
                "SELECT api_key_encrypted FROM user_provider_settings WHERE user_id = ? AND provider = ?",
                (user.id, "kimi"),
            ).fetchone()
            assert prow is None or prow["api_key_encrypted"] is None

        # The global model/base URL are safe defaults, but authenticated beta
        # accounts must supply their own credential.
        cfg = provider_settings_service.resolve_litellm_config(user.id)
        assert cfg["provider"] == "kimi"
        assert cfg["model"] == "openai/kimi-for-coding"
        assert cfg["api_key"] is None
        assert cfg["base_url"] == "https://api.kimi.com/coding/v1"

        ready, msg = provider_settings_service.provider_ready_for_build(user.id)
        assert ready is False
        assert "API key" in msg

        # user can still explicitly enter/override a key in Settings → Cloud & AI
        configured = provider_settings_service.update_provider_settings(
            user.id,
            ProviderSettingsUpdate(provider="kimi", model="kimi-for-coding", api_key="sk-user-entered-kimi"),
        )
        assert configured.has_api_key is True
        assert configured.is_active is True

        final_cfg = provider_settings_service.resolve_litellm_config(user.id)
        assert final_cfg["api_key"] == "sk-user-entered-kimi"  # user key takes precedence

        # Clearing the user key returns the account to BYOK-not-configured.
        cleared = provider_settings_service.clear_provider_key(user.id, "kimi")
        assert cleared.has_api_key is False
        fallback_cfg = provider_settings_service.resolve_litellm_config(user.id)
        assert fallback_cfg["api_key"] is None

        # Private/self-hosted deployments can deliberately opt into one shared key.
        settings.allow_shared_provider_keys = True
        shared = provider_settings_service.get_active_provider_settings(user.id)
        assert shared.has_api_key is True
        assert provider_settings_service.resolve_litellm_config(user.id)["api_key"] == "sk-kimi-from-env"
    finally:
        for k, v in original.items():
            setattr(settings, k, v)
