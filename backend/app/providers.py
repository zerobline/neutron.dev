from dataclasses import dataclass
from typing import Literal

from app.models import ProviderName

AuthMethod = Literal["api_key", "oauth"]


@dataclass(frozen=True)
class ProviderDefinition:
    id: ProviderName
    label: str
    default_model: str
    litellm_prefix: str | None
    default_base_url: str | None = None
    requires_base_url: bool = False
    requires_api_key: bool = True
    auth_method: AuthMethod = "api_key"


PROVIDERS: dict[ProviderName, ProviderDefinition] = {
    "openai": ProviderDefinition("openai", "OpenAI", "gpt-4o", "openai"),
    "anthropic": ProviderDefinition("anthropic", "Anthropic", "claude-sonnet-4-20250514", "anthropic"),
    "moonshot": ProviderDefinition("moonshot", "Moonshot", "kimi-k2", "moonshot", "https://api.moonshot.ai/v1"),
    "kimi": ProviderDefinition("kimi", "Kimi", "kimi-for-coding", "openai", "https://api.kimi.com/coding/v1"),
    "openrouter": ProviderDefinition("openrouter", "OpenRouter", "openai/gpt-4o-mini", "openrouter", "https://openrouter.ai/api/v1"),
    "groq": ProviderDefinition("groq", "Groq", "llama-3.3-70b-versatile", "groq"),
    "xai": ProviderDefinition("xai", "Grok / xAI", "grok-3-mini", "xai"),
    "xai-oauth": ProviderDefinition(
        "xai-oauth",
        "Grok OAuth (SuperGrok)",
        "grok-4.20-reasoning",
        "xai",
        "https://api.x.ai/v1",
        requires_api_key=False,
        auth_method="oauth",
    ),
    "nvidia": ProviderDefinition("nvidia", "NVIDIA", "llama-3.3-nemotron-super-49b-v1.5", "nvidia"),
    "mistral": ProviderDefinition("mistral", "Mistral", "mistral-large-latest", "mistral", "https://api.mistral.ai/v1"),
    "openai-compatible": ProviderDefinition("openai-compatible", "OpenAI-Compatible", "", "openai", None, True, False),
    "custom": ProviderDefinition("custom", "Custom", "", None, None, False, False),
}


MODEL_OPTIONS = [
    {"value": "openai/gpt-4o", "label": "OpenAI GPT-4o"},
    {"value": "openai/gpt-4o-mini", "label": "OpenAI GPT-4o Mini"},
    {"value": "anthropic/claude-sonnet-4-20250514", "label": "Anthropic Claude Sonnet"},
    {"value": "moonshot/kimi-k2", "label": "Moonshot Kimi K2"},
    {"value": "kimi/kimi-for-coding", "label": "Kimi for Coding"},
    {"value": "openrouter/openai/gpt-4o-mini", "label": "OpenRouter GPT-4o Mini"},
    {"value": "groq/llama-3.3-70b-versatile", "label": "Groq Llama 3.3 70B"},
    {"value": "xai/grok-3-mini", "label": "Grok 3 Mini"},
    {"value": "xai/grok-4.20-reasoning", "label": "Grok 4.20 Reasoning (OAuth)"},
    {"value": "nvidia/llama-3.3-nemotron-super-49b-v1.5", "label": "NVIDIA Llama Nemotron Super 1.5 (49B)"},
    {"value": "mistral/mistral-large-latest", "label": "Mistral Large"},
]


def get_provider(provider: ProviderName) -> ProviderDefinition:
    return PROVIDERS[provider]


def prefixed_model(provider: ProviderName, model: str) -> str:
    definition = get_provider(provider)
    cleaned = model.strip()
    if provider == "custom" or definition.litellm_prefix is None:
        return cleaned
    if cleaned.startswith(f"{definition.litellm_prefix}/"):
        return cleaned
    return f"{definition.litellm_prefix}/{cleaned}"


def provider_model(provider: ProviderName, model: str) -> str:
    definition = get_provider(provider)
    cleaned = model.strip()
    if definition.litellm_prefix and cleaned.startswith(f"{definition.litellm_prefix}/"):
        return cleaned.removeprefix(f"{definition.litellm_prefix}/")
    return cleaned
