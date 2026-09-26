from typing import cast

import pytest

from app.config import cors_allowed_origins, session_cookie_samesite, settings, validate_production_settings
from app.models import ProviderName


def test_settings_defaults():
    assert settings.llm_model == "ollama/llama3.1"
    assert settings.host == "0.0.0.0"
    assert settings.port == 8000
    assert settings.projects_dir.exists()
    assert "atoms_test_projects_" in str(settings.projects_dir)


def test_projects_dir_created():
    # The conftest module sets a temp projects dir; ensure it exists.
    assert settings.projects_dir.is_dir()


def test_provider_inference_and_effective_models():
    original = {
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "openai_base_url": settings.openai_base_url,
        "openai_api_key": settings.openai_api_key,
        "moonshot_api_key": settings.moonshot_api_key,
        "moonshot_base_url": settings.moonshot_base_url,
    }
    try:
        settings.llm_provider = None
        settings.openai_base_url = None
        settings.llm_model = "openai/gpt-4o"
        assert settings.infer_provider() == "openai"
        assert settings.effective_litellm_config()["model"] == "openai/gpt-4o"

        settings.llm_model = "gpt-4o"
        assert settings.effective_litellm_config()["model"] == "openai/gpt-4o"

        settings.llm_provider = "openai-compatible"
        settings.llm_model = "kimchi/kimi-k2.7"
        settings.openai_base_url = "http://localhost:20128/v1"
        config = settings.effective_litellm_config()
        assert config["model"] == "openai/kimchi/kimi-k2.7"
        assert config["base_url"] == "http://localhost:20128/v1"

        settings.llm_provider = "moonshot"
        settings.llm_model = "moonshotai/Kimi-K2.5"
        config = settings.effective_litellm_config()
        assert config["model"] == "moonshot/moonshotai/Kimi-K2.5"
        assert config["base_url"] == "https://api.moonshot.ai/v1"

        settings.llm_provider = "custom"
        settings.llm_model = "vendor/model"
        assert settings.effective_litellm_config()["model"] == "vendor/model"
    finally:
        for key, value in original.items():
            setattr(settings, key, value)


def test_infer_provider_moonshot():
    settings.llm_provider = None
    settings.llm_model = "moonshot/kimi-k2"
    assert settings.infer_provider() == "moonshot"


def test_infer_provider_gpt_prefix():
    settings.llm_provider = None
    settings.openai_base_url = None
    settings.llm_model = "gpt-4o-mini"
    assert settings.infer_provider() == "openai"


def test_infer_provider_base_url_without_openai_prefix():
    settings.llm_provider = None
    settings.openai_base_url = "http://localhost:1234/v1"
    settings.llm_model = "custom-model"
    assert settings.infer_provider() == "custom"


def test_infer_provider_openai_with_base_url():
    settings.llm_provider = None
    settings.openai_base_url = "http://localhost:1234/v1"
    settings.llm_model = "openai/some-model"
    assert settings.infer_provider() == "openai-compatible"


def test_provider_model_strips_moonshot_prefix():
    settings.llm_provider = "moonshot"
    settings.llm_model = "moonshot/kimi-k2"
    assert settings.provider_model() == "kimi-k2"


def test_apply_provider_settings_moonshot_base_url():
    settings.apply_provider_settings(
        provider="moonshot",
        model="kimi-k2",
        base_url="https://custom.moonshot.ai/v1",
    )
    assert settings.moonshot_base_url == "https://custom.moonshot.ai/v1"


def test_apply_provider_settings_moonshot_clear_api_key():
    settings.moonshot_api_key = "old-key"
    settings.apply_provider_settings(
        provider="moonshot",
        model="kimi-k2",
        clear_api_key=True,
    )
    assert settings.moonshot_api_key is None


def test_apply_provider_settings_moonshot_blank_base_url_resets_default():
    settings.apply_provider_settings(
        provider="moonshot",
        model="kimi-k2",
        base_url="",
    )
    assert settings.moonshot_base_url == "https://api.moonshot.ai/v1"


def test_apply_provider_settings_moonshot_api_key():
    settings.apply_provider_settings(
        provider="moonshot",
        model="kimi-k2",
        api_key="new-moon-key",
    )
    assert settings.moonshot_api_key == "new-moon-key"


def test_infer_provider_kimi():
    settings.llm_provider = None
    settings.llm_model = "kimi/kimi-for-coding"
    assert settings.infer_provider() == "kimi"


def test_infer_provider_bare_kimi_for_coding():
    settings.llm_provider = None
    settings.llm_model = "kimi-for-coding"
    assert settings.infer_provider() == "kimi"
    assert settings.effective_litellm_config()["model"] == "openai/kimi-for-coding"


def test_infer_provider_openrouter():
    settings.llm_provider = None
    settings.llm_model = "openrouter/kimi-for-coding"
    assert settings.infer_provider() == "openrouter"


def test_provider_model_strips_kimi_prefix():
    settings.llm_provider = "kimi"
    settings.llm_model = "kimi/kimi-for-coding"
    assert settings.provider_model() == "kimi-for-coding"


def test_provider_model_strips_openrouter_prefix():
    settings.llm_provider = "openrouter"
    settings.llm_model = "openrouter/kimi-for-coding"
    assert settings.provider_model() == "kimi-for-coding"


def test_effective_litellm_config_kimi():
    original = {
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "kimi_api_key": settings.kimi_api_key,
        "kimi_base_url": settings.kimi_base_url,
    }
    try:
        settings.llm_provider = "kimi"
        settings.llm_model = "kimi-for-coding"
        settings.kimi_api_key = "test-kimi-key"
        config = settings.effective_litellm_config()
        assert config["model"] == "openai/kimi-for-coding"
        assert config["api_key"] == "test-kimi-key"
        assert config["base_url"] == "https://api.kimi.com/coding/v1"
        assert config["provider"] == "kimi"
    finally:
        for key, value in original.items():
            setattr(settings, key, value)


def test_effective_litellm_config_openrouter():
    original = {
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "openrouter_api_key": settings.openrouter_api_key,
        "openrouter_base_url": settings.openrouter_base_url,
    }
    try:
        settings.llm_provider = "openrouter"
        settings.llm_model = "kimi-for-coding"
        settings.openrouter_api_key = "test-or-key"
        config = settings.effective_litellm_config()
        assert config["model"] == "openrouter/kimi-for-coding"
        assert config["api_key"] == "test-or-key"
        assert config["base_url"] == "https://openrouter.ai/api/v1"
        assert config["provider"] == "openrouter"
    finally:
        for key, value in original.items():
            setattr(settings, key, value)


def test_apply_provider_settings_kimi_api_key():
    settings.apply_provider_settings(
        provider="kimi",
        model="kimi-for-coding",
        api_key="new-kimi-key",
    )
    assert settings.kimi_api_key == "new-kimi-key"


def test_apply_provider_settings_kimi_clear_api_key():
    settings.kimi_api_key = "old-key"
    settings.apply_provider_settings(
        provider="kimi",
        model="kimi-for-coding",
        clear_api_key=True,
    )
    assert settings.kimi_api_key is None


def test_apply_provider_settings_kimi_base_url():
    settings.apply_provider_settings(
        provider="kimi",
        model="kimi-for-coding",
        base_url="https://custom.kimi.ai/v1",
    )
    assert settings.kimi_base_url == "https://custom.kimi.ai/v1"


def test_apply_provider_settings_kimi_blank_base_url_resets_default():
    settings.apply_provider_settings(
        provider="kimi",
        model="kimi-for-coding",
        base_url="",
    )
    assert settings.kimi_base_url == "https://api.kimi.com/coding/v1"


def test_apply_provider_settings_openrouter_api_key():
    settings.apply_provider_settings(
        provider="openrouter",
        model="kimi-for-coding",
        api_key="new-or-key",
    )
    assert settings.openrouter_api_key == "new-or-key"


def test_apply_provider_settings_openrouter_clear_api_key():
    settings.openrouter_api_key = "old-key"
    settings.apply_provider_settings(
        provider="openrouter",
        model="kimi-for-coding",
        clear_api_key=True,
    )
    assert settings.openrouter_api_key is None


def test_apply_provider_settings_openrouter_base_url():
    settings.apply_provider_settings(
        provider="openrouter",
        model="kimi-for-coding",
        base_url="https://custom.openrouter.ai/v1",
    )
    assert settings.openrouter_base_url == "https://custom.openrouter.ai/v1"


def test_apply_provider_settings_openrouter_blank_base_url_resets_default():
    settings.apply_provider_settings(
        provider="openrouter",
        model="kimi-for-coding",
        base_url="",
    )
    assert settings.openrouter_base_url == "https://openrouter.ai/api/v1"


def test_apply_provider_settings_openai_base_url():
    settings.apply_provider_settings(
        provider="openai",
        model="gpt-4o",
        base_url="https://custom.openai.com/v1",
    )
    assert settings.openai_base_url == "https://custom.openai.com/v1"


def test_apply_provider_settings_openai_clear_api_key():
    settings.openai_api_key = "old-key"
    settings.apply_provider_settings(
        provider="openai",
        model="gpt-4o",
        clear_api_key=True,
    )
    assert settings.openai_api_key is None


def test_apply_provider_settings_openai_api_key():
    settings.apply_provider_settings(
        provider="openai",
        model="gpt-4o",
        api_key="new-openai-key",
    )
    assert settings.openai_api_key == "new-openai-key"


def test_available_models_response_includes_presets():
    resp = settings.available_models_response()
    assert "models" in resp
    assert "current" in resp
    values = [m["value"] for m in resp["models"]]
    assert "openai/gpt-4o" in values
    assert "kimi/kimi-for-coding" in values
    assert "openrouter/moonshotai/kimi-k2-0711-code" in values


def test_available_models_response_adds_current_if_missing():
    original = settings.llm_model
    try:
        settings.llm_model = "custom/unique-model"
        resp = settings.available_models_response()
        assert resp["current"] == "custom/unique-model"
        assert resp["models"][0]["value"] == "custom/unique-model"
    finally:
        settings.llm_model = original


def test_provider_settings_response():
    original = {
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
    }
    try:
        settings.llm_provider = "openai"
        settings.llm_model = "openai/gpt-4o"
        resp = settings.provider_settings_response()
        assert resp["provider"] == "openai"
        assert resp["model"] == "gpt-4o"
        assert resp["effective_model"] == "openai/gpt-4o"
        assert isinstance(resp["has_api_key"], bool)
    finally:
        for key, value in original.items():
            setattr(settings, key, value)


def test_openai_compatible_requires_base_url():
    original_provider = settings.llm_provider
    original_model = settings.llm_model
    original_base_url = settings.openai_base_url
    try:
        settings.llm_provider = "openai-compatible"
        settings.llm_model = "kimchi/kimi-k2.7"
        settings.openai_base_url = None
        try:
            settings.effective_litellm_config()
        except ValueError as exc:
            assert str(exc) == "OpenAI-compatible provider requires a base URL."
        else:
            raise AssertionError("Expected base URL validation error")
    finally:
        settings.llm_provider = original_provider
        settings.llm_model = original_model
        settings.openai_base_url = original_base_url


def test_all_provider_inference_model_stripping_api_keys_and_config_branches():
    original = {
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "anthropic_api_key": settings.anthropic_api_key,
        "groq_api_key": settings.groq_api_key,
        "xai_api_key": settings.xai_api_key,
        "nvidia_api_key": settings.nvidia_api_key,
    }
    try:
        cases = [
            ("anthropic", "anthropic/claude-sonnet-4-20250514", "anthropic", "claude-sonnet-4-20250514", "anthropic/claude-sonnet-4-20250514", "anthropic_api_key"),
            ("anthropic", "claude-3-5-sonnet", "anthropic", "claude-3-5-sonnet", "anthropic/claude-3-5-sonnet", "anthropic_api_key"),
            ("groq", "groq/llama-3.3-70b-versatile", "groq", "llama-3.3-70b-versatile", "groq/llama-3.3-70b-versatile", "groq_api_key"),
            ("xai", "xai/grok-3-mini", "xai", "grok-3-mini", "xai/grok-3-mini", "xai_api_key"),
            ("xai", "grok-3-mini", "xai", "grok-3-mini", "xai/grok-3-mini", "xai_api_key"),

            ("nvidia", "nvidia/llama-3.3-nemotron-super-49b-v1.5", "nvidia", "llama-3.3-nemotron-super-49b-v1.5", "nvidia/llama-3.3-nemotron-super-49b-v1.5", "nvidia_api_key"),
            ("nvidia", "nvidia_nim/llama-3.3-nemotron-super-49b-v1.5", "nvidia", "llama-3.3-nemotron-super-49b-v1.5", "nvidia/llama-3.3-nemotron-super-49b-v1.5", "nvidia_api_key"),
            ("mistral", "mistral/mistral-large-latest", "mistral", "mistral-large-latest", "mistral/mistral-large-latest", "mistral_api_key"),
            ("mistral", "mistral-small", "mistral", "mistral-small", "mistral/mistral-small", "mistral_api_key"),
        ]
        for provider, model, inferred, stripped, effective, key_attr in cases:
            settings.llm_provider = None
            settings.llm_model = model
            setattr(settings, key_attr, f"{provider}-key")
            provider_name = cast(ProviderName, inferred)
            assert settings.infer_provider() == provider_name
            assert settings.provider_model(provider_name) == stripped
            config = settings.effective_litellm_config()
            assert config["model"] == effective
            assert config["api_key"] == f"{provider}-key"

        for provider, key_attr in [
            ("anthropic", "anthropic_api_key"),
            ("groq", "groq_api_key"),
            ("xai", "xai_api_key"),
            ("nvidia", "nvidia_api_key"),
            ("mistral", "mistral_api_key"),
        ]:
            provider_name = cast(ProviderName, provider)
            setattr(settings, key_attr, "old-key")
            settings.apply_provider_settings(provider=provider_name, model="model", clear_api_key=True)
            assert getattr(settings, key_attr) is None
            settings.apply_provider_settings(provider=provider_name, model="model", api_key="new-key")
            assert getattr(settings, key_attr) == "new-key"

        settings.openai_base_url = "old-base"
        settings.apply_provider_settings(provider="groq", model="model", base_url="ignored")
        assert settings.openai_base_url == "old-base"
    finally:
        for key, value in original.items():
            setattr(settings, key, value)


def test_cors_allowed_origins_includes_frontend_and_localhost():
    original = settings.frontend_url
    try:
        settings.frontend_url = "https://app.vercel.app, https://preview.vercel.app"
        assert cors_allowed_origins() == [
            "https://app.vercel.app",
            "https://preview.vercel.app",
            "http://localhost:3000",
        ]
    finally:
        settings.frontend_url = original


def test_validate_production_settings_requires_secure_cookie_and_encryption_key():
    original = {
        "app_env": settings.app_env,
        "cookie_secure": settings.cookie_secure,
        "credential_encryption_key": settings.credential_encryption_key,
    }
    try:
        settings.app_env = "production"
        settings.cookie_secure = False
        settings.credential_encryption_key = None
        with pytest.raises(RuntimeError, match="COOKIE_SECURE"):
            validate_production_settings()
        settings.cookie_secure = True
        with pytest.raises(RuntimeError, match="CREDENTIAL_ENCRYPTION_KEY"):
            validate_production_settings()
        settings.credential_encryption_key = "test-key"
        validate_production_settings()
    finally:
        for key, value in original.items():
            setattr(settings, key, value)


def test_validate_production_settings_is_noop_outside_production():
    original = settings.app_env
    try:
        settings.app_env = "development"
        validate_production_settings()
    finally:
        settings.app_env = original


def test_cors_does_not_add_localhost_in_production():
    original_env = settings.app_env
    original_url = settings.frontend_url
    try:
        settings.app_env = "production"
        settings.frontend_url = "https://beta.example.com"
        assert cors_allowed_origins() == ["https://beta.example.com"]
    finally:
        settings.app_env = original_env
        settings.frontend_url = original_url


def test_session_cookie_samesite_follows_cookie_secure_flag():
    original = settings.cookie_secure
    try:
        settings.cookie_secure = False
        assert session_cookie_samesite() == "lax"
        settings.cookie_secure = True
        assert session_cookie_samesite() == "none"
    finally:
        settings.cookie_secure = original


def test_xai_oauth_provider_config_branch():
    original = {
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "xai_api_key": settings.xai_api_key,
    }
    try:
        settings.llm_provider = "xai-oauth"
        settings.llm_model = "xai/grok-4.5"
        settings.xai_api_key = "oauth-token"
        config = settings.effective_litellm_config()
        assert config == {
            "provider": "xai-oauth",
            "model": "xai/grok-4.5",
            "api_key": "oauth-token",
            "base_url": "https://api.x.ai/v1",
        }
        assert settings.provider_model("xai-oauth") == "grok-4.5"
    finally:
        for key, value in original.items():
            setattr(settings, key, value)


def test_infer_provider_mistral_bare_and_prefixed():
    original = settings.llm_model
    try:
        settings.llm_provider = None
        settings.llm_model = "mistral-large-latest"
        assert settings.infer_provider() == "mistral"
        settings.llm_model = "mistral/mistral-small"
        assert settings.infer_provider() == "mistral"
    finally:
        settings.llm_model = original


def test_infer_provider_nvidia_variants():
    original = settings.llm_model
    try:
        settings.llm_provider = None
        settings.llm_model = "nvidia/llama"
        assert settings.infer_provider() == "nvidia"
        settings.llm_model = "nvidia_nim/llama"
        assert settings.infer_provider() == "nvidia"
    finally:
        settings.llm_model = original


def test_infer_provider_xai_variants():
    original = settings.llm_model
    try:
        settings.llm_provider = None
        settings.llm_model = "xai/grok"
        assert settings.infer_provider() == "xai"
        settings.llm_model = "grok-foo"
        assert settings.infer_provider() == "xai"
    finally:
        settings.llm_model = original


def test_infer_provider_custom_fallback():
    original_provider = settings.llm_provider
    original_model = settings.llm_model
    original_base = settings.openai_base_url
    try:
        settings.llm_provider = None
        settings.openai_base_url = None
        settings.llm_model = "vendor/unknown-model"
        assert settings.infer_provider() == "custom"
    finally:
        settings.llm_provider = original_provider
        settings.llm_model = original_model
        settings.openai_base_url = original_base


def test_apply_provider_settings_custom_clears_openai_key():
    settings.openai_api_key = "some"
    settings.apply_provider_settings(provider="custom", model="foo/bar", clear_api_key=True)
    assert settings.openai_api_key is None


def test_apply_provider_settings_various_providers_base_and_key():
    originals = {
        "anthropic_api_key": settings.anthropic_api_key,
        "groq_api_key": settings.groq_api_key,
        "xai_api_key": settings.xai_api_key,
        "nvidia_api_key": settings.nvidia_api_key,
        "mistral_api_key": settings.mistral_api_key,
        "openai_base_url": settings.openai_base_url,
    }
    try:
        # base_url branches for providers that use openai_base_url
        settings.apply_provider_settings(provider="openai-compatible", model="m", base_url="http://ex/v1")
        assert settings.openai_base_url == "http://ex/v1"
        settings.apply_provider_settings(provider="custom", model="m2", base_url="http://c/v1")
        assert settings.openai_base_url == "http://c/v1"

        for prov, key_attr in [
            ("anthropic", "anthropic_api_key"),
            ("groq", "groq_api_key"),
            ("xai", "xai_api_key"),
            ("nvidia", "nvidia_api_key"),
            ("mistral", "mistral_api_key"),
        ]:
            p = cast(ProviderName, prov)
            setattr(settings, key_attr, None)
            settings.apply_provider_settings(provider=p, model="mod", api_key="k1")
            assert getattr(settings, key_attr) == "k1"
            settings.apply_provider_settings(provider=p, model="mod", clear_api_key=True)
            assert getattr(settings, key_attr) is None
    finally:
        for k, v in originals.items():
            setattr(settings, k, v)


def test_infer_provider_gemini_prefixed_and_bare():
    original_provider = settings.llm_provider
    original_model = settings.llm_model
    try:
        settings.llm_provider = None
        settings.llm_model = "gemini/gemini-3.5-flash-lite"
        assert settings.infer_provider() == "gemini"
        settings.llm_model = "gemini-3.5-flash-lite"
        assert settings.infer_provider() == "gemini"
    finally:
        settings.llm_provider = original_provider
        settings.llm_model = original_model


def test_effective_litellm_config_gemini():
    original = {
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "gemini_api_key": settings.gemini_api_key,
    }
    try:
        settings.llm_provider = "gemini"
        settings.llm_model = "gemini-3.5-flash-lite"
        settings.gemini_api_key = "test-gemini-key"
        config = settings.effective_litellm_config()
        assert config == {
            "provider": "gemini",
            "model": "gemini/gemini-3.5-flash-lite",
            "api_key": "test-gemini-key",
            "base_url": None,
        }
        assert settings.provider_model("gemini") == "gemini-3.5-flash-lite"
    finally:
        for key, value in original.items():
            setattr(settings, key, value)


def test_apply_provider_settings_gemini_key():
    original = settings.gemini_api_key
    try:
        settings.gemini_api_key = "old-key"
        settings.apply_provider_settings(
            provider="gemini",
            model="gemini-3.5-flash-lite",
            clear_api_key=True,
        )
        assert settings.gemini_api_key is None
        settings.apply_provider_settings(
            provider="gemini",
            model="gemini-3.5-flash-lite",
            api_key="new-key",
        )
        assert settings.gemini_api_key == "new-key"
    finally:
        settings.gemini_api_key = original
