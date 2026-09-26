import time

import pytest

from app.database import db_connection
from app.models import ProviderSettingsUpdate, UserCreate
from app.services import auth_service, model_catalog_service
from app.services.credential_crypto import encrypt_api_key


def make_user(email="models@example.com"):
    return auth_service.create_user(UserCreate(email=email, password="password123"))


@pytest.fixture(autouse=True)
def clear_cache():
    model_catalog_service.clear_model_cache()
    yield
    model_catalog_service.clear_model_cache()


def test_custom_provider_returns_current_model_only(temp_db):
    user = make_user()
    # Clear any seeded provider row for custom (create_user now seeds global's model for the default provider)
    with db_connection() as conn:
        conn.execute(
            "DELETE FROM user_provider_settings WHERE user_id = ? AND provider = 'custom'",
            (user.id,),
        )
        conn.commit()
    result = model_catalog_service.list_provider_models(user.id, "custom")
    assert result.provider == "custom"
    assert result.source == "fallback"
    assert result.current == ""
    assert result.models == []


def test_fallback_without_credentials_uses_catalog(temp_db, monkeypatch):
    user = make_user()

    monkeypatch.setattr(
        "app.services.model_catalog_service._catalog_models",
        lambda provider: ["gpt-4o", "text-embedding-3-small", "gpt-4o-mini"],
    )

    result = model_catalog_service.list_provider_models(user.id, "openai")

    assert result.source == "catalog"
    assert any(model.value == "gpt-4o" for model in result.models)
    assert all("embed" not in model.value for model in result.models)
    assert result.current == "gpt-4o"


def test_api_sync_when_credentials_present(temp_db, monkeypatch):
    user = make_user()
    from app.services import provider_settings_service

    provider_settings_service.update_provider_settings(
        user.id,
        ProviderSettingsUpdate(provider="openai", model="gpt-4o", api_key="sk-test"),
    )

    monkeypatch.setattr(
        "app.services.model_catalog_service._fetch_models_from_api",
        lambda provider, api_key, base_url: ["gpt-4o", "gpt-4o-mini"],
    )

    result = model_catalog_service.list_provider_models(user.id, "openai")

    assert result.source == "api"
    assert [model.value for model in result.models] == ["gpt-4o", "gpt-4o-mini"]


def test_api_sync_empty_falls_back_to_catalog(temp_db, monkeypatch):
    user = make_user()
    from app.services import provider_settings_service

    provider_settings_service.update_provider_settings(
        user.id,
        ProviderSettingsUpdate(provider="groq", model="llama-3.3-70b-versatile", api_key="gsk-test"),
    )

    monkeypatch.setattr("app.services.model_catalog_service._fetch_models_from_api", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        "app.services.model_catalog_service._catalog_models",
        lambda provider: ["llama-3.3-70b-versatile"],
    )

    result = model_catalog_service.list_provider_models(user.id, "groq")

    assert result.source == "catalog"
    assert result.models[0].value == "llama-3.3-70b-versatile"


def test_cache_hit_reuses_models(temp_db, monkeypatch):
    user = make_user()
    from app.services import provider_settings_service

    provider_settings_service.update_provider_settings(
        user.id,
        ProviderSettingsUpdate(provider="openai", model="gpt-4o", api_key="sk-test"),
    )

    calls = {"count": 0}

    def fake_fetch(provider, api_key, base_url):
        calls["count"] += 1
        return ["gpt-4o"]

    monkeypatch.setattr("app.services.model_catalog_service._fetch_models_from_api", fake_fetch)

    first = model_catalog_service.list_provider_models(user.id, "openai")
    second = model_catalog_service.list_provider_models(user.id, "openai")

    assert first.source == "api"
    assert second.source == "api"
    assert calls["count"] == 1


def test_expired_cache_refetches(temp_db, monkeypatch):
    user = make_user()
    from app.services import provider_settings_service

    provider_settings_service.update_provider_settings(
        user.id,
        ProviderSettingsUpdate(provider="openai", model="gpt-4o", api_key="sk-test"),
    )

    calls = {"count": 0}

    def fake_fetch(provider, api_key, base_url):
        calls["count"] += 1
        return ["gpt-4o"]

    monkeypatch.setattr("app.services.model_catalog_service._fetch_models_from_api", fake_fetch)

    model_catalog_service.list_provider_models(user.id, "openai")
    for key in list(model_catalog_service._cache):
        expires_at, models, source = model_catalog_service._cache[key]
        model_catalog_service._cache[key] = (time.time() - 1, models, source)

    model_catalog_service.list_provider_models(user.id, "openai")
    assert calls["count"] == 2


def test_current_model_is_injected_when_missing_from_sync(temp_db, monkeypatch):
    user = make_user()
    from app.services import provider_settings_service

    provider_settings_service.update_provider_settings(
        user.id,
        ProviderSettingsUpdate(provider="openai", model="custom-model", api_key="sk-test"),
    )

    monkeypatch.setattr(
        "app.services.model_catalog_service._fetch_models_from_api",
        lambda *args, **kwargs: ["gpt-4o"],
    )

    result = model_catalog_service.list_provider_models(user.id, "openai")

    assert result.models[0].value == "custom-model"
    assert result.current == "custom-model"


def test_openai_compatible_requires_base_url_for_sync(temp_db, monkeypatch):
    user = make_user()

    monkeypatch.setattr(
        "app.services.model_catalog_service._catalog_models",
        lambda provider: ["local-model"],
    )

    result = model_catalog_service.list_provider_models(user.id, "openai-compatible")
    assert result.source == "catalog"
    assert any(model.value == "local-model" for model in result.models)

    from app.services import provider_settings_service

    provider_settings_service.update_provider_settings(
        user.id,
        ProviderSettingsUpdate(
            provider="openai-compatible",
            model="local-model",
            base_url="http://localhost:1234/v1",
        ),
    )
    monkeypatch.setattr(
        "app.services.model_catalog_service._fetch_models_from_api",
        lambda *args, **kwargs: ["local-model", "other-model"],
    )

    synced = model_catalog_service.list_provider_models(user.id, "openai-compatible")
    assert synced.source == "api"
    assert len(synced.models) == 2


def test_xai_oauth_uses_access_token(temp_db, monkeypatch):
    user = make_user("oauth-models@example.com")
    from app.services import provider_settings_service, xai_oauth_service

    xai_oauth_service.store_oauth_tokens(
        user.id,
        xai_oauth_service.OAuthTokens(access_token="oauth-token", refresh_token="refresh", expires_at=9999999999),
    )
    provider_settings_service.update_provider_settings(
        user.id,
        ProviderSettingsUpdate(provider="xai-oauth", model="grok-4.5", base_url="https://api.x.ai/v1"),
    )

    captured: dict[str, str | None] = {}

    def fake_fetch(provider, api_key, base_url):
        captured["api_key"] = api_key
        return ["grok-4.5"]

    monkeypatch.setattr("app.services.model_catalog_service._fetch_models_from_api", fake_fetch)

    result = model_catalog_service.list_provider_models(user.id, "xai-oauth")

    assert captured["api_key"] == "oauth-token"
    assert result.source == "api"


def test_xai_oauth_token_failure_falls_back(temp_db, monkeypatch):
    user = make_user("oauth-fallback@example.com")

    monkeypatch.setattr(
        "app.services.model_catalog_service.xai_oauth_service.ensure_fresh_access_token",
        lambda _user_id: (_ for _ in ()).throw(RuntimeError("oauth down")),
    )
    monkeypatch.setattr(
        "app.services.model_catalog_service._catalog_models",
        lambda provider: ["grok-4.5"],
    )

    result = model_catalog_service.list_provider_models(user.id, "xai-oauth")
    assert result.source == "catalog"
    assert any(model.value == "grok-4.5" for model in result.models)


def test_normalize_and_filter_helpers():
    assert model_catalog_service._normalize_model("nvidia", "nvidia_nim/nvidia/llama-3.3-nemotron-super-49b-v1.5") == (
        "llama-3.3-nemotron-super-49b-v1.5"
    )
    assert model_catalog_service._normalize_model("nvidia", "nvidia/llama-3.3-nemotron-super-49b-v1.5") == (
        "llama-3.3-nemotron-super-49b-v1.5"
    )
    assert model_catalog_service._normalize_model("nvidia", "nvidia_nim/meta/llama-3.1-70b-instruct") == "meta/llama-3.1-70b-instruct"
    assert model_catalog_service._normalize_model("groq", "groq/llama-3.3-70b-versatile") == "llama-3.3-70b-versatile"
    assert model_catalog_service._normalize_model("mistral", "mistral/mistral-large-latest") == "mistral-large-latest"
    assert model_catalog_service._normalize_model("openai", "   ") == ""
    assert model_catalog_service._is_chat_model("text-embedding-3-small") is False
    assert model_catalog_service._is_chat_model("gpt-4o") is True
    assert model_catalog_service._dedupe(["a", "a", "", "b"]) == ["a", "b"]
    assert model_catalog_service._model_label("gpt-4o-mini") == "gpt 4o mini"
    assert model_catalog_service._fetch_models_from_api("custom", None, None) == []


def test_provider_credentials_for_custom_provider(temp_db):
    user = make_user("custom-creds@example.com")
    assert model_catalog_service._provider_credentials(user.id, "custom") == (None, None, False)


def test_fetch_models_from_api_normalizes_output(monkeypatch):
    monkeypatch.setattr(
        "app.services.model_catalog_service.get_valid_models",
        lambda **kwargs: ["openai/gpt-4o", "text-embedding-3-small"],
    )
    models = model_catalog_service._fetch_models_from_api("openai", "sk-test", None)
    assert models == ["gpt-4o"]


def test_fetch_models_from_api_strips_v1_suffix_for_xai(monkeypatch):
    captured: dict = {}

    def fake_get_valid_models(**kwargs):
        captured.update(kwargs)
        return ["xai/grok-3-mini"]

    monkeypatch.setattr("app.services.model_catalog_service.get_valid_models", fake_get_valid_models)
    models = model_catalog_service._fetch_models_from_api("xai-oauth", "token", "https://api.x.ai/v1")
    assert models == ["grok-3-mini"]
    assert captured["api_base"] == "https://api.x.ai"


def test_litellm_api_base_passthrough_for_non_xai():
    assert model_catalog_service._litellm_api_base("openai", "https://example.com/v1") == "https://example.com/v1"
    assert model_catalog_service._litellm_api_base("xai", None) is None


def test_catalog_models_returns_empty_for_custom():
    assert model_catalog_service._catalog_models("custom") == []


def test_catalog_models_reads_litellm_provider_list(monkeypatch):
    monkeypatch.setattr(
        "app.services.model_catalog_service.get_valid_models",
        lambda **kwargs: ["openai/gpt-4o", "text-embedding-3-small"],
    )
    models = model_catalog_service._catalog_models("openai")
    assert models == ["gpt-4o"]


def test_fallback_restores_default_when_catalog_filtered_out(monkeypatch):
    monkeypatch.setattr("app.services.model_catalog_service._is_chat_model", lambda _model: False)
    models, source = model_catalog_service._fallback_models("openai", "")
    assert models == ["gpt-4o"]
    assert source == "fallback"


def test_fallback_restores_current_when_no_default(monkeypatch):
    monkeypatch.setattr("app.services.model_catalog_service._is_chat_model", lambda _model: False)
    models, source = model_catalog_service._fallback_models("openai-compatible", "manual-model")
    assert models == ["manual-model"]
    assert source == "fallback"


def test_fallback_uses_default_and_current_when_catalog_filtered(temp_db, monkeypatch):
    user = make_user("filtered-default@example.com")
    monkeypatch.setattr("app.services.model_catalog_service._catalog_models", lambda provider: [])
    monkeypatch.setattr("app.services.model_catalog_service._preset_models", lambda provider: [])

    models, source = model_catalog_service._fallback_models("openai", "")
    assert source == "catalog"
    assert models == ["gpt-4o"]

    models, source = model_catalog_service._fallback_models("openai-compatible", "saved-only")
    assert "saved-only" in models


def test_fallback_source_when_no_models_available(temp_db, monkeypatch):
    user = make_user("empty-fallback@example.com")
    monkeypatch.setattr("app.services.model_catalog_service._current_model", lambda _uid, _provider: "")
    monkeypatch.setattr("app.services.model_catalog_service._catalog_models", lambda provider: [])
    monkeypatch.setattr("app.services.model_catalog_service._preset_models", lambda provider: [])

    result = model_catalog_service.list_provider_models(user.id, "openai-compatible")
    assert result.source == "fallback"
    assert result.models == []


def test_cache_hit_without_current_model(temp_db, monkeypatch):
    user = make_user("cache-no-current@example.com")
    from app.services import provider_settings_service

    provider_settings_service.update_provider_settings(
        user.id,
        ProviderSettingsUpdate(provider="openai", model="gpt-4o", api_key="sk-test"),
    )
    monkeypatch.setattr("app.services.model_catalog_service._current_model", lambda _uid, _provider: "")
    monkeypatch.setattr(
        "app.services.model_catalog_service._fetch_models_from_api",
        lambda *args, **kwargs: ["gpt-4o"],
    )

    model_catalog_service.list_provider_models(user.id, "openai")
    second = model_catalog_service.list_provider_models(user.id, "openai")

    assert second.models[0].value == "gpt-4o"


def test_current_model_reads_saved_value(temp_db):
    user = make_user("current-model@example.com")
    from app.services import provider_settings_service

    provider_settings_service.update_provider_settings(
        user.id,
        ProviderSettingsUpdate(provider="anthropic", model="claude-sonnet-4-20250514", api_key="anthropic-key"),
        activate=False,
    )

    assert model_catalog_service._current_model(user.id, "anthropic") == "claude-sonnet-4-20250514"


def test_cached_current_model_is_prepended(temp_db, monkeypatch):
    user = make_user("cached-current@example.com")
    from app.services import provider_settings_service

    provider_settings_service.update_provider_settings(
        user.id,
        ProviderSettingsUpdate(provider="openai", model="saved-model", api_key="sk-test"),
    )
    monkeypatch.setattr(
        "app.services.model_catalog_service._fetch_models_from_api",
        lambda *args, **kwargs: ["gpt-4o"],
    )

    first = model_catalog_service.list_provider_models(user.id, "openai")
    provider_settings_service.update_provider_settings(
        user.id,
        ProviderSettingsUpdate(provider="openai", model="another-model", api_key="sk-test"),
        activate=False,
    )
    second = model_catalog_service.list_provider_models(user.id, "openai")

    assert first.current == "saved-model"
    assert second.current == "another-model"
    assert second.models[0].value == "another-model"


def test_fallback_without_catalog_uses_current_model(temp_db, monkeypatch):
    user = make_user("only-current@example.com")
    from app.services import provider_settings_service

    provider_settings_service.update_provider_settings(
        user.id,
        ProviderSettingsUpdate(provider="openai-compatible", model="only-model", base_url="http://localhost:20128/v1"),
        activate=False,
    )

    monkeypatch.setattr("app.services.model_catalog_service._fetch_models_from_api", lambda *args, **kwargs: [])
    monkeypatch.setattr("app.services.model_catalog_service._catalog_models", lambda provider: [])
    monkeypatch.setattr("app.services.model_catalog_service._preset_models", lambda provider: [])

    result = model_catalog_service.list_provider_models(user.id, "openai-compatible")
    assert result.current == "only-model"
    assert any(model.value == "only-model" for model in result.models)

def test_gemini_model_normalization_and_catalog_provider(monkeypatch):
    assert model_catalog_service._litellm_provider("gemini") == "gemini"
    assert model_catalog_service._normalize_model(
        "gemini",
        "gemini/gemini-3.5-flash-lite",
    ) == "gemini-3.5-flash-lite"
    monkeypatch.setattr(
        "app.services.model_catalog_service.get_valid_models",
        lambda **kwargs: [
            "gemini/gemini-3.5-flash-lite",
            "gemini/text-embedding-004",
        ],
    )
    models = model_catalog_service._catalog_models("gemini")
    assert "gemini-3.5-flash-lite" in models
    assert all("embed" not in model.lower() for model in models)
