from typing import Literal
from urllib.parse import urlparse

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator


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
ProviderAuthMethod = Literal["api_key", "oauth"]
SearchProviderName = Literal["brave", "serper", "tavily", "exa"]
OAuthPollStatus = Literal["pending", "complete", "expired", "denied"]
CustomMcpTransport = Literal["stdio", "sse", "http"]
DefaultMcpKey = Literal["github", "linear"]
MAX_CUSTOM_MCP_SERVERS = 20
DEFAULT_MCP_KEYS: tuple[DefaultMcpKey, ...] = ("github", "linear")


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=20000)
    template: str | None = Field(default=None, max_length=100)
    stack: str | None = Field(default=None, max_length=32)


class BuildTokenUsage(BaseModel):
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    successful_requests: int = 0


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str
    status: str
    template: str | None
    stack: str = "static"
    created_at: str
    updated_at: str
    token_usage: BuildTokenUsage = Field(default_factory=BuildTokenUsage)
    token_budget: int = 0
    token_budget_percent: float | None = None


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=200)
    display_name: str | None = Field(default=None, max_length=100)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("display_name")
    @classmethod
    def trim_display_name(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class UserLogin(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str | None
    created_at: str


class AuthResponse(UserResponse):
    """Public authentication response; the session stays in an HttpOnly cookie."""


class ProjectFileResponse(BaseModel):
    file_path: str
    content: str


class MessageResponse(BaseModel):
    id: int
    project_id: str
    role: str
    agent: str | None
    content: str
    created_at: str
    kind: str | None = None
    metadata: dict | None = None


class AgentModelEntry(BaseModel):
    id: str
    label: str
    model: str
    is_override: bool = False


class AgentModelsResponse(BaseModel):
    provider: str
    default_model: str
    agents: list[AgentModelEntry]


class AgentModelsUpdate(BaseModel):
    models: dict[str, str | None] = Field(default_factory=dict)


class UserMessage(BaseModel):
    content: str


class CustomMcpServerConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=100)
    transport: CustomMcpTransport
    command_or_url: str = Field(
        min_length=1,
        max_length=500,
        validation_alias=AliasChoices("command_or_url", "commandOrUrl"),
        serialization_alias="command_or_url",
    )
    notes: str = Field(default="", max_length=1000)

    @field_validator("id", "name", "command_or_url", "notes", mode="before")
    @classmethod
    def trim_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_endpoint(self):
        if self.transport in {"http", "sse"}:
            parsed = urlparse(self.command_or_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("Remote MCP servers must start with http:// or https://.")
        return self


class DefaultMcpConfig(BaseModel):
    """Built-in MCP integrations that CrewAI agents attach via the native `mcps` field."""

    model_config = ConfigDict(populate_by_name=True)

    key: DefaultMcpKey
    enabled: bool = True

    @field_validator("key", mode="before")
    @classmethod
    def normalize_key(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


def default_mcp_configs() -> list[DefaultMcpConfig]:
    return [DefaultMcpConfig(key=key, enabled=True) for key in DEFAULT_MCP_KEYS]


class ProjectConnectorSettings(BaseModel):
    """Project MCP connector settings.

    GitHub and Linear are included by default and resolved to real CrewAI MCP
    server configs when credentials are available. Custom remote servers are
    attached as HTTP/SSE MCPs; custom STDIO entries stay metadata-only unless
    the backend explicitly allows local process execution.
    """

    default_mcps: list[DefaultMcpConfig] = Field(default_factory=default_mcp_configs)
    custom_mcp_servers: list[CustomMcpServerConfig] = Field(default_factory=list, max_length=MAX_CUSTOM_MCP_SERVERS)

    @model_validator(mode="after")
    def ensure_unique_default_keys(self):
        seen: set[str] = set()
        unique: list[DefaultMcpConfig] = []
        for item in self.default_mcps:
            if item.key in seen:
                continue
            seen.add(item.key)
            unique.append(item)
        # Always surface the built-in defaults even if a client omits them.
        for key in DEFAULT_MCP_KEYS:
            if key not in seen:
                unique.append(DefaultMcpConfig(key=key, enabled=True))
        self.default_mcps = unique
        return self


SkillAgentTarget = Literal[
    "all",
    "team_leader",
    "product_manager",
    "architect",
    "engineer",
    "data_scientist",
]
SKILL_AGENT_TARGETS: tuple[SkillAgentTarget, ...] = (
    "all",
    "team_leader",
    "product_manager",
    "architect",
    "engineer",
    "data_scientist",
)
MAX_SKILLS_PER_PROJECT = 30


class SkillAssignment(BaseModel):
    """Which agents receive a named skill pack on this project."""

    name: str = Field(min_length=1, max_length=64)
    enabled: bool = False
    agents: list[SkillAgentTarget] = Field(default_factory=lambda: ["all"])

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value):
        if not isinstance(value, str):
            return value
        return value.strip().lower().replace("_", "-")

    @field_validator("agents", mode="before")
    @classmethod
    def normalize_agents(cls, value):
        if value is None or value == []:
            return ["all"]
        if isinstance(value, str):
            value = [value]
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            key = item.strip().lower() if isinstance(item, str) else item
            if key in seen:
                continue
            seen.add(str(key))
            cleaned.append(key)
        return cleaned or ["all"]

    @model_validator(mode="after")
    def collapse_all(self):
        if "all" in self.agents:
            self.agents = ["all"]
        return self


class ProjectSkillSettings(BaseModel):
    """Project skill toggles and agent targeting.

    Built-in and custom skills are resolved from the filesystem; this file only
    stores which skills are enabled and which agents receive them.
    """

    skills: list[SkillAssignment] = Field(default_factory=list, max_length=MAX_SKILLS_PER_PROJECT)

    @model_validator(mode="after")
    def ensure_unique_skill_names(self):
        seen: set[str] = set()
        unique: list[SkillAssignment] = []
        for item in self.skills:
            if item.name in seen:
                continue
            seen.add(item.name)
            unique.append(item)
        self.skills = unique
        return self


class SkillCatalogItem(BaseModel):
    name: str
    description: str
    source: Literal["builtin", "custom"]
    recommended_agents: list[str] = Field(default_factory=list)
    enabled: bool = False
    agents: list[SkillAgentTarget] = Field(default_factory=lambda: ["all"])
    body_preview: str | None = None


class ProjectSkillsResponse(BaseModel):
    skills: list[SkillCatalogItem]


class ProjectSkillsUpdate(BaseModel):
    skills: list[SkillAssignment] = Field(default_factory=list, max_length=MAX_SKILLS_PER_PROJECT)


class SkillCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=1024)
    body: str = Field(min_length=1, max_length=50000)
    agents: list[SkillAgentTarget] = Field(default_factory=lambda: ["all"])
    enabled: bool = True

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value):
        if not isinstance(value, str):
            return value
        return value.strip().lower().replace("_", "-")

    @field_validator("description", "body", mode="before")
    @classmethod
    def trim_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("agents", mode="before")
    @classmethod
    def normalize_agents(cls, value):
        if value is None or value == []:
            return ["all"]
        if isinstance(value, str):
            value = [value]
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            key = item.strip().lower() if isinstance(item, str) else item
            if key in seen:
                continue
            seen.add(str(key))
            cleaned.append(key)
        return cleaned or ["all"]


class AgentEvent(BaseModel):
    type: str
    agent: str | None = None
    task: str | None = None
    content: str | None = None
    file_path: str | None = None
    files: list[str] | None = None
    message: str | None = None


class ModelOption(BaseModel):
    value: str
    label: str


class AvailableModelsResponse(BaseModel):
    models: list[ModelOption]
    current: str


class ProviderModelsResponse(BaseModel):
    provider: ProviderName
    models: list[ModelOption]
    current: str
    source: Literal["api", "catalog", "fallback"] = "fallback"


class ProviderSettingsResponse(BaseModel):
    provider: ProviderName
    model: str
    base_url: str | None
    has_api_key: bool
    effective_model: str


class ProviderSummary(ProviderSettingsResponse):
    label: str
    is_active: bool
    requires_base_url: bool = False
    requires_api_key: bool = True
    auth_method: ProviderAuthMethod = "api_key"
    is_connected: bool = False


class ProviderListResponse(BaseModel):
    providers: list[ProviderSummary]
    active_provider: ProviderName


class OAuthDeviceStartResponse(BaseModel):
    session_id: str
    verification_uri: str
    user_code: str
    expires_in: int
    interval: int


class OAuthDevicePollRequest(BaseModel):
    session_id: str = Field(min_length=1)


class OAuthDevicePollResponse(BaseModel):
    status: OAuthPollStatus
    connected: bool = False
    interval: int | None = None


class ProviderSettingsUpdate(BaseModel):
    provider: ProviderName
    model: str = Field(min_length=1)
    api_key: str | None = None
    base_url: str | None = None
    clear_api_key: bool = False

    @model_validator(mode="after")
    def validate_settings(self):
        self.model = self.model.strip()
        if not self.model:
            raise ValueError("Model is required")
        if self.base_url is not None:
            self.base_url = self.base_url.strip() or None
        if self.api_key is not None:
            self.api_key = self.api_key.strip() or None
        return self


class SearchProviderSummary(BaseModel):
    provider: SearchProviderName
    label: str
    description: str
    docs_url: str
    has_api_key: bool
    has_user_api_key: bool


class SearchProviderListResponse(BaseModel):
    providers: list[SearchProviderSummary]


class SearchProviderSettingsUpdate(BaseModel):
    provider: SearchProviderName
    api_key: str | None = Field(default=None, max_length=4096)

    @field_validator("api_key")
    @classmethod
    def trim_api_key(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class McpConnectorSummary(BaseModel):
    key: DefaultMcpKey
    label: str
    description: str
    docs_url: str
    connection_url: str
    default_url: str
    has_api_key: bool
    has_user_api_key: bool
    enabled_by_default: bool = True


class McpConnectorListResponse(BaseModel):
    connectors: list[McpConnectorSummary]


class McpConnectorSettingsUpdate(BaseModel):
    key: DefaultMcpKey
    api_key: str | None = Field(default=None, max_length=4096)

    @field_validator("api_key")
    @classmethod
    def trim_api_key(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @field_validator("key", mode="before")
    @classmethod
    def normalize_key(cls, value):
        return value.strip().lower() if isinstance(value, str) else value
