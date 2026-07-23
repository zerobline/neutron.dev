from __future__ import annotations

import time
from typing import Literal

from litellm import get_valid_models

from app.database import db_connection
from app.models import ModelOption, ProviderModelsResponse, ProviderName
from app.providers import MODEL_OPTIONS, get_provider, provider_model
from app.services.credential_crypto import decrypt_api_key
from app.services import xai_oauth_service

ModelSource = Literal["api", "catalog", "fallback"]
CACHE_TTL_SECONDS = 600

_LITELLM_PROVIDER_MAP: dict[ProviderName, str | None] = {
    "openai": "openai",
    "anthropic": "anthropic",
    "moonshot": "moonshot",
    "kimi": "openai",
    "openrouter": "openrouter",
    "groq": "groq",
    "xai": "xai",
    "xai-oauth": "xai",
    "nvidia": "nvidia_nim",
    "mistral": "mistral",
    "openai-compatible": "openai",
    "custom": None,
}

_EXCLUDED_MODEL_MARKERS = (
    "embed",
    "moderation",
    "rerank",
    "whisper",
    "tts",
    "dall-e",
    "sora",
    "transcribe",
    "image",
    "audio",
    "realtime",
)

_cache: dict[str, tuple[float, list[str], ModelSource]] = {}


def clear_model_cache() -> None:
    _cache.clear()


def _cache_key(user_id: str, provider: ProviderName, api_key: str | None, base_url: str | None) -> str:
    return f"{user_id}:{provider}:{api_key or ''}:{base_url or ''}"


def _litellm_provider(provider: ProviderName) -> str | None:
    return _LITELLM_PROVIDER_MAP.get(provider)


def _normalize_model(provider: ProviderName, raw_model: str) -> str:
    cleaned = raw_model.strip()
    if not cleaned:
        return ""

    litellm_provider = _litellm_provider(provider)
    if litellm_provider and cleaned.startswith(f"{litellm_provider}/"):
        cleaned = cleaned.removeprefix(f"{litellm_provider}/")

    if provider == "nvidia" and cleaned.startswith("nvidia/"):
        cleaned = cleaned.removeprefix("nvidia/")

    return provider_model(provider, cleaned)


def _is_chat_model(model_id: str) -> bool:
    lowered = model_id.lower()
    return not any(marker in lowered for marker in _EXCLUDED_MODEL_MARKERS)


def _model_label(model_id: str) -> str:
    return model_id.replace("/", " / ").replace("-", " ").replace("_", " ")


def _dedupe(models: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for model in models:
        if not model or model in seen:
            continue
        seen.add(model)
        ordered.append(model)
    return ordered


def _provider_credentials(user_id: str, provider: ProviderName) -> tuple[str | None, str | None, bool]:
    definition = get_provider(provider)
    with db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM user_provider_settings WHERE user_id = ? AND provider = ?",
            (user_id, provider),
        ).fetchone()

    base_url = row["base_url"] if row and row["base_url"] is not None else definition.default_base_url

    if provider == "xai-oauth":
        try:
            api_key = xai_oauth_service.ensure_fresh_access_token(user_id)
        except Exception:
            api_key = None
        return api_key, base_url, bool(api_key)

    if provider == "custom":
        return None, base_url, False

    api_key = decrypt_api_key(row["api_key_encrypted"] if row else None)

    if provider == "openai-compatible":
        return api_key, base_url, bool(base_url)

    return api_key, base_url, bool(api_key)


def _current_model(user_id: str, provider: ProviderName) -> str:
    definition = get_provider(provider)
    with db_connection() as conn:
        row = conn.execute(
            "SELECT model FROM user_provider_settings WHERE user_id = ? AND provider = ?",
            (user_id, provider),
        ).fetchone()
    if row and row["model"]:
        return row["model"]
    return definition.default_model


def _preset_models(provider: ProviderName) -> list[str]:
    definition = get_provider(provider)
    prefix = definition.litellm_prefix
    models: list[str] = []
    for option in MODEL_OPTIONS:
        value = option["value"]
        if prefix and value.startswith(f"{prefix}/"):
            models.append(value.removeprefix(f"{prefix}/"))
    return models


def _catalog_models(provider: ProviderName) -> list[str]:
    litellm_provider = _litellm_provider(provider)
    if litellm_provider is None:
        return []

    raw_models = get_valid_models(custom_llm_provider=litellm_provider, check_provider_endpoint=False)
    normalized = [_normalize_model(provider, model) for model in raw_models]
    return [model for model in normalized if model and _is_chat_model(model)]


def _litellm_api_base(litellm_provider: str, base_url: str | None) -> str | None:
    # litellm's XAI client appends /v1/models to api_base, so a base ending in /v1
    # would produce /v1/v1/models and a 404.
    if litellm_provider == "xai" and base_url:
        return base_url.removesuffix("/v1")
    return base_url


def _fetch_models_from_api(provider: ProviderName, api_key: str | None, base_url: str | None) -> list[str]:
    litellm_provider = _litellm_provider(provider)
    if litellm_provider is None:
        return []

    base_url = _litellm_api_base(litellm_provider, base_url)
    raw_models = get_valid_models(
        custom_llm_provider=litellm_provider,
        check_provider_endpoint=True,
        api_key=api_key,
        api_base=base_url,
    )
    normalized = [_normalize_model(provider, model) for model in raw_models]
    return [model for model in normalized if model and _is_chat_model(model)]


def _fallback_models(provider: ProviderName, current: str) -> tuple[list[str], ModelSource]:
    definition = get_provider(provider)
    seeds = [definition.default_model, current, *_preset_models(provider), *_catalog_models(provider)]
    models = _dedupe([seed for seed in seeds if seed and _is_chat_model(seed)])
    source: ModelSource = "catalog" if models else "fallback"
    if not models and definition.default_model:
        models = [definition.default_model]
    if not models and current:
        models = [current]
    if not models:
        source = "fallback"
    return models, source


def _to_options(models: list[str]) -> list[ModelOption]:
    return [ModelOption(value=model, label=_model_label(model)) for model in models]


def list_provider_models(user_id: str, provider: ProviderName) -> ProviderModelsResponse:
    if provider == "custom":
        current = _current_model(user_id, provider)
        models = _dedupe([current] if current else [])
        return ProviderModelsResponse(provider=provider, models=_to_options(models), current=current, source="fallback")

    current = _current_model(user_id, provider)
    api_key, base_url, can_sync = _provider_credentials(user_id, provider)

    if not can_sync:
        models, source = _fallback_models(provider, current)
        models = _dedupe([*models, current] if current else models)
        return ProviderModelsResponse(provider=provider, models=_to_options(models), current=current, source=source)

    cache_key = _cache_key(user_id, provider, api_key, base_url)
    cached = _cache.get(cache_key)
    if cached and cached[0] > time.time():
        models = _dedupe(cached[1])
        if current:
            models = [current, *[model for model in models if model != current]]
        return ProviderModelsResponse(provider=provider, models=_to_options(models), current=current, source=cached[2])

    api_models = _fetch_models_from_api(provider, api_key, base_url)
    if api_models:
        models = _dedupe(api_models)
        source: ModelSource = "api"
    else:
        models, source = _fallback_models(provider, current)

    if current and current not in models:
        models.insert(0, current)

    _cache[cache_key] = (time.time() + CACHE_TTL_SECONDS, models, source)
    return ProviderModelsResponse(provider=provider, models=_to_options(models), current=current, source=source)