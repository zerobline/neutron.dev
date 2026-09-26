from pathlib import Path
from typing import Literal, cast

from dotenv import load_dotenv
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

ProviderName = Literal[
    "openai",
    "anthropic",
    "gemini",
    "openai-compatible",
    "moonshot",
    "kimi",
    "openrouter",
    "groq",
    "xai",
    "xai-oauth",
    "nvidia",
    "mistral",
    "custom",
]


class Settings(BaseSettings):
    app_env: Literal["development", "test", "production"] = "development"
    llm_model: str = "openai/gpt-4o"
    llm_provider: ProviderName | None = None
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    )
    groq_api_key: str | None = None
    xai_api_key: str | None = None
    nvidia_api_key: str | None = None
    mistral_api_key: str | None = None
    moonshot_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("MOONSHOT_API_KEY", "KIMI_API_KEY"),
    )
    moonshot_base_url: str = "https://api.moonshot.ai/v1"
    kimi_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("KIMI_API_KEY", "MOONSHOT_API_KEY"),
    )
    kimi_base_url: str = "https://api.kimi.com/coding/v1"
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    mistral_base_url: str = "https://api.mistral.ai/v1"
    serper_api_key: str | None = None
    host: str = "0.0.0.0"
    port: int = 8000
    projects_dir: Path = Path(__file__).resolve().parent.parent / "projects"
    skills_dir: Path = Path(__file__).resolve().parent.parent / "skills"
    max_skill_body_chars: int = 20000
    max_custom_skills_per_project: int = 20
    frontend_url: str = "http://localhost:3000"
    auth_session_days: int = 30
    cookie_secure: bool = False
    credential_encryption_key: str | None = None
    allow_shared_provider_keys: bool = False
    crew_planning: bool = False
    # CrewAI console verbose logging (agent thoughts / tool use in server logs).
    # Keep True in local dev so you can follow what agents are doing; set False in prod.
    crew_verbose: bool = True
    agent_max_iter: int = 6
    engineer_max_iter: int = 18
    agent_max_execution_seconds: int = 240
    engineer_max_execution_seconds: int = 600
    agent_max_retry_limit: int = 1
    task_guardrail_max_retries: int = 2
    max_prompt_chars: int = 20000
    max_upload_file_context_chars: int = 20000
    max_upload_context_chars: int = 60000
    max_upload_file_bytes: int = 10 * 1024 * 1024
    max_upload_project_bytes: int = 50 * 1024 * 1024
    max_upload_files_per_project: int = 20
    max_concurrent_builds: int = 3
    max_build_tokens: int = 80000
    # Next.js live preview (docker: install Node in the backend image + publish ports)
    runtime_bind_host: str = "127.0.0.1"
    runtime_public_host: str = "127.0.0.1"
    runtime_port_base: int = 3100
    runtime_port_span: int = 50
    # Built-in MCP integrations (CrewAI native `mcps` field)
    github_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GITHUB_TOKEN", "GITHUB_PERSONAL_ACCESS_TOKEN", "GH_TOKEN"),
    )
    github_mcp_url: str = "https://api.githubcopilot.com/mcp/"
    github_mcp_command: str = "npx"
    github_mcp_args: str = "-y @modelcontextprotocol/server-github"
    linear_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LINEAR_API_KEY", "LINEAR_TOKEN"),
    )
    linear_mcp_url: str = "https://mcp.linear.app/mcp"
    linear_mcp_command: str = "npx"
    linear_mcp_args: str = "-y mcp-remote https://mcp.linear.app/sse"
    mcp_prefer_remote: bool = True
    mcp_allow_custom_stdio: bool = False
    mcp_cache_tools_list: bool = True

    model_config = {"env_file": ".env", "extra": "ignore"}

    def infer_provider(self) -> ProviderName:
        if self.llm_provider:
            return self.llm_provider
        model = self.llm_model.strip().lower()
        if model.startswith("kimi/") or model in {"kimi-for-coding", "kimi-k2.6", "kimi-k2-0711-preview"}:
            return "kimi"
        if model.startswith("moonshot/"):
            return "moonshot"
        if model.startswith("anthropic/") or model.startswith("claude-"):
            return "anthropic"
        if model.startswith("gemini/") or model.startswith("gemini-"):
            return "gemini"
        if model.startswith("openrouter/"):
            return "openrouter"
        if model.startswith("groq/"):
            return "groq"
        if model.startswith("xai/") or model.startswith("grok-"):
            return "xai"
        if model.startswith("nvidia_nim/") or model.startswith("nvidia/"):
            return "nvidia"
        if model.startswith("mistral/") or model.startswith("mistral-"):
            return "mistral"
        if self.openai_base_url and model.startswith("openai/"):
            return "openai-compatible"
        if model.startswith("openai/") or model.startswith("gpt-"):
            return "openai"
        return "custom"

    def provider_model(self, provider: ProviderName | None = None) -> str:
        provider = provider or self.infer_provider()
        model = self.llm_model.strip()
        if provider in {"openai", "openai-compatible"} and model.startswith("openai/"):
            return model.removeprefix("openai/")
        if provider == "moonshot" and model.startswith("moonshot/"):
            return model.removeprefix("moonshot/")
        if provider == "gemini" and model.startswith("gemini/"):
            return model.removeprefix("gemini/")
        if provider == "kimi" and model.startswith("kimi/"):
            return model.removeprefix("kimi/")
        if provider == "openrouter" and model.startswith("openrouter/"):
            return model.removeprefix("openrouter/")
        if provider == "anthropic" and model.startswith("anthropic/"):
            return model.removeprefix("anthropic/")
        if provider == "groq" and model.startswith("groq/"):
            return model.removeprefix("groq/")
        if provider in {"xai", "xai-oauth"} and model.startswith("xai/"):
            return model.removeprefix("xai/")
        if provider == "nvidia" and model.startswith("nvidia_nim/"):
            return model.removeprefix("nvidia_nim/")
        if provider == "nvidia" and model.startswith("nvidia/"):
            return model.removeprefix("nvidia/")
        if provider == "mistral" and model.startswith("mistral/"):
            return model.removeprefix("mistral/")
        return model

    def default_model_for_provider(self, provider: ProviderName | None = None) -> str:
        """Return the (unprefixed) model string derived from global settings for the provider."""
        provider = provider or self.infer_provider()
        return self.provider_model(provider)

    def default_base_url_for_provider(self, provider: ProviderName | None = None) -> str | None:
        """Return the base URL derived from global settings for the provider (or its definition default later)."""
        provider = provider or self.infer_provider()
        return self._provider_base_url(provider)

    def get_api_key_for_provider(self, provider: ProviderName) -> str | None:
        """API key from .env / global config for the given provider (fallback for user settings)."""
        return self._provider_api_key(provider)

    def get_base_url_for_provider(self, provider: ProviderName) -> str | None:
        """Base URL from .env / global config for the given provider (fallback for user settings)."""
        return self._provider_base_url(provider)

    def _provider_api_key(self, provider: ProviderName) -> str | None:
        if provider == "moonshot":
            return self.moonshot_api_key
        if provider == "kimi":
            return self.kimi_api_key
        if provider == "openrouter":
            return self.openrouter_api_key
        if provider == "anthropic":
            return self.anthropic_api_key
        if provider == "gemini":
            return self.gemini_api_key
        if provider == "groq":
            return self.groq_api_key
        if provider in {"xai", "xai-oauth"}:
            return self.xai_api_key
        if provider == "nvidia":
            return self.nvidia_api_key
        if provider == "mistral":
            return self.mistral_api_key
        return self.openai_api_key

    def _provider_base_url(self, provider: ProviderName) -> str | None:
        if provider == "moonshot":
            return self.moonshot_base_url
        if provider == "kimi":
            return self.kimi_base_url
        if provider == "openrouter":
            return self.openrouter_base_url
        if provider == "mistral":
            return self.mistral_base_url
        return self.openai_base_url

    def _prefixed_model(self, prefix: str, model: str) -> str:
        return model if model.startswith(f"{prefix}/") else f"{prefix}/{model}"

    def effective_litellm_config(self) -> dict[str, str | None]:
        provider = self.infer_provider()
        model = self.provider_model(provider)
        base_url = self._provider_base_url(provider)
        api_key = self._provider_api_key(provider)

        if provider == "openai-compatible":
            if not base_url:
                raise ValueError("OpenAI-compatible provider requires a base URL.")
            return {
                "provider": provider,
                "model": self._prefixed_model("openai", model),
                "api_key": api_key,
                "base_url": base_url,
            }
        if provider == "openai":
            return {
                "provider": provider,
                "model": self._prefixed_model("openai", model),
                "api_key": api_key,
                "base_url": base_url,
            }
        if provider == "moonshot":
            return {
                "provider": provider,
                "model": self._prefixed_model("moonshot", model),
                "api_key": api_key,
                "base_url": base_url,
            }
        if provider == "kimi":
            return {
                "provider": provider,
                "model": self._prefixed_model("openai", model),
                "api_key": api_key,
                "base_url": base_url,
            }
        if provider == "openrouter":
            return {
                "provider": provider,
                "model": self._prefixed_model("openrouter", model),
                "api_key": api_key,
                "base_url": base_url,
            }
        if provider == "anthropic":
            return {
                "provider": provider,
                "model": self._prefixed_model("anthropic", model),
                "api_key": api_key,
                "base_url": base_url,
            }
        if provider == "gemini":
            return {
                "provider": provider,
                "model": self._prefixed_model("gemini", model),
                "api_key": api_key,
                "base_url": None,
            }
        if provider == "groq":
            return {
                "provider": provider,
                "model": self._prefixed_model("groq", model),
                "api_key": api_key,
                "base_url": base_url,
            }
        if provider == "xai":
            return {
                "provider": provider,
                "model": self._prefixed_model("xai", model),
                "api_key": api_key,
                "base_url": base_url,
            }
        if provider == "xai-oauth":
            return {
                "provider": provider,
                "model": self._prefixed_model("xai", model),
                "api_key": api_key,
                "base_url": base_url or "https://api.x.ai/v1",
            }
        if provider == "mistral":
            return {
                "provider": provider,
                "model": self._prefixed_model("mistral", model),
                "api_key": api_key,
                "base_url": base_url,
            }
        if provider == "nvidia":
            return {
                "provider": provider,
                "model": self._prefixed_model("nvidia", model),
                "api_key": api_key,
                "base_url": base_url,
            }
        return {
            "provider": provider,
            "model": self.llm_model.strip(),
            "api_key": api_key,
            "base_url": base_url,
        }

    MODEL_PRESETS: list[dict[str, str]] = [
        {"value": "openai/gpt-4o", "label": "OpenAI GPT-4o"},
        {"value": "openai/gpt-4o-mini", "label": "OpenAI GPT-4o Mini"},
        {"value": "anthropic/claude-sonnet-4-20250514", "label": "Claude Sonnet"},
        {"value": "gemini/gemini-3.5-flash-lite", "label": "Google Gemini 3.5 Flash-Lite"},
        {"value": "mistral/mistral-large-latest", "label": "Mistral Large"},
        {"value": "moonshot/kimi-k2", "label": "Moonshot Kimi K2"},
        {"value": "kimi/kimi-for-coding", "label": "Kimi K2.7 Code"},
        {"value": "openrouter/moonshotai/kimi-k2-0711-code", "label": "OpenRouter Kimi K2.7 Code"},
        {"value": "groq/llama-3.3-70b-versatile", "label": "Groq Llama 3.3 70B"},
        {"value": "xai/grok-3-mini", "label": "Grok 3 Mini"},
        {"value": "xai/grok-4.20-reasoning", "label": "Grok 4.20 Reasoning (OAuth)"},
        {"value": "nvidia/llama-3.3-nemotron-super-49b-v1.5", "label": "NVIDIA Llama Nemotron Super 1.5 (49B)"},
    ]

    def available_models_response(self) -> dict:
        presets = [dict(p) for p in self.MODEL_PRESETS]
        current = self.llm_model.strip()
        if not any(p["value"] == current for p in presets):
            presets.insert(0, {"value": current, "label": current})
        return {"models": presets, "current": current}

    def provider_settings_response(self) -> dict[str, str | bool | None]:
        config = self.effective_litellm_config()
        provider = cast(ProviderName, config["provider"])
        return {
            "provider": provider,
            "model": self.provider_model(provider),
            "base_url": config["base_url"],
            "has_api_key": bool(config["api_key"]),
            "effective_model": config["model"],
        }

    def apply_provider_settings(
        self,
        provider: ProviderName,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        clear_api_key: bool = False,
    ) -> None:
        self.llm_provider = provider
        self.llm_model = model.strip()

        if base_url is not None:
            cleaned_base_url = base_url.strip() or None
            if provider == "moonshot":
                self.moonshot_base_url = cleaned_base_url or "https://api.moonshot.ai/v1"
            elif provider == "kimi":
                self.kimi_base_url = cleaned_base_url or "https://api.kimi.com/coding/v1"
            elif provider == "openrouter":
                self.openrouter_base_url = cleaned_base_url or "https://openrouter.ai/api/v1"
            elif provider in {"openai", "openai-compatible", "custom"}:
                self.openai_base_url = cleaned_base_url

        if clear_api_key:
            if provider == "moonshot":
                self.moonshot_api_key = None
            elif provider == "kimi":
                self.kimi_api_key = None
            elif provider == "openrouter":
                self.openrouter_api_key = None
            elif provider == "anthropic":
                self.anthropic_api_key = None
            elif provider == "gemini":
                self.gemini_api_key = None
            elif provider == "groq":
                self.groq_api_key = None
            elif provider == "xai":
                self.xai_api_key = None
            elif provider == "nvidia":
                self.nvidia_api_key = None
            elif provider == "mistral":
                self.mistral_api_key = None
            else:
                self.openai_api_key = None
            return

        cleaned_api_key = api_key.strip() if api_key else ""
        if cleaned_api_key:
            if provider == "moonshot":
                self.moonshot_api_key = cleaned_api_key
            elif provider == "kimi":
                self.kimi_api_key = cleaned_api_key
            elif provider == "openrouter":
                self.openrouter_api_key = cleaned_api_key
            elif provider == "anthropic":
                self.anthropic_api_key = cleaned_api_key
            elif provider == "gemini":
                self.gemini_api_key = cleaned_api_key
            elif provider == "groq":
                self.groq_api_key = cleaned_api_key
            elif provider == "xai":
                self.xai_api_key = cleaned_api_key
            elif provider == "nvidia":
                self.nvidia_api_key = cleaned_api_key
            elif provider == "mistral":
                self.mistral_api_key = cleaned_api_key
            else:
                self.openai_api_key = cleaned_api_key


settings = Settings()
settings.projects_dir.mkdir(parents=True, exist_ok=True)


def cors_allowed_origins() -> list[str]:
    origins = [part.strip() for part in settings.frontend_url.split(",") if part.strip()]
    if settings.app_env != "production" and "http://localhost:3000" not in origins:
        origins.append("http://localhost:3000")
    return origins


def session_cookie_samesite() -> Literal["lax", "none"]:
    return "none" if settings.cookie_secure else "lax"


def validate_production_settings() -> None:
    if settings.app_env != "production":
        return
    if not settings.cookie_secure:
        raise RuntimeError("COOKIE_SECURE must be true when APP_ENV=production.")
    if not settings.credential_encryption_key:
        raise RuntimeError(
            "CREDENTIAL_ENCRYPTION_KEY must be set when APP_ENV=production. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
