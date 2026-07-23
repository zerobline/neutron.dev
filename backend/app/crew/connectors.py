import json
import shlex
from typing import Type
from urllib.parse import urlsplit, urlunsplit

from crewai.mcp import MCPServerHTTP, MCPServerSSE, MCPServerStdio
from crewai.mcp.config import MCPServerConfig
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from app.config import settings
from app.mcp_connectors import get_mcp_connector
from app.models import (
    DEFAULT_MCP_KEYS,
    DefaultMcpConfig,
    ProjectConnectorSettings,
    default_mcp_configs,
)
from app.services.mcp_connector_settings_service import resolve_mcp_api_key


CONNECTORS_FILE = "connectors.json"

_DEFAULT_LABELS = {
    "github": "GitHub",
    "linear": "Linear",
}


def _connectors_path(project_id: str):
    return settings.projects_dir / project_id / CONNECTORS_FILE


def load_project_connectors(project_id: str) -> ProjectConnectorSettings:
    path = _connectors_path(project_id)
    if not path.exists():
        return ProjectConnectorSettings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ProjectConnectorSettings()
    return ProjectConnectorSettings.model_validate(data)


def save_project_connectors(project_id: str, connector_settings: ProjectConnectorSettings) -> ProjectConnectorSettings:
    path = _connectors_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(connector_settings.model_dump_json(indent=2), encoding="utf-8")
    return connector_settings


def merge_connector_settings(
    saved: ProjectConnectorSettings,
    inline: ProjectConnectorSettings | dict | None,
) -> ProjectConnectorSettings:
    if inline is None:
        return saved
    inline_settings = inline if isinstance(inline, ProjectConnectorSettings) else ProjectConnectorSettings.model_validate(inline)

    default_by_key = {item.key: item for item in saved.default_mcps}
    for item in inline_settings.default_mcps:
        default_by_key[item.key] = item
    merged_defaults = [
        default_by_key.get(key, DefaultMcpConfig(key=key, enabled=True))
        for key in DEFAULT_MCP_KEYS
    ]

    by_id = {server.id: server for server in saved.custom_mcp_servers}
    for server in inline_settings.custom_mcp_servers:
        by_id[server.id] = server
    return ProjectConnectorSettings(
        default_mcps=merged_defaults,
        custom_mcp_servers=list(by_id.values()),
    )


def _safe_remote_url(value: str) -> str:
    parsed = urlsplit(value)
    netloc = parsed.hostname or ""
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def _split_command(command_or_url: str) -> tuple[str, list[str]]:
    parts = shlex.split(command_or_url, posix=True)
    if not parts:
        return "", []
    return parts[0], parts[1:]


def _parse_args(raw: str) -> list[str]:
    raw = (raw or "").strip()
    if not raw:
        return []
    return shlex.split(raw, posix=True)


def _auth_headers(token: str | None) -> dict[str, str] | None:
    if not token:
        return None
    return {"Authorization": f"Bearer {token}"}


def _default_enabled(connector_settings: ProjectConnectorSettings, key: str) -> bool:
    for item in connector_settings.default_mcps or default_mcp_configs():
        if item.key == key:
            return item.enabled
    return key in DEFAULT_MCP_KEYS


def _resolve_github_mcp(token: str | None) -> MCPServerConfig | None:
    # Only attach when the user has configured a credential in the UI (or local env fallback).
    if not token:
        return None
    if settings.mcp_prefer_remote and settings.github_mcp_url:
        return MCPServerHTTP(
            url=settings.github_mcp_url,
            headers=_auth_headers(token),
            streamable=True,
            cache_tools_list=settings.mcp_cache_tools_list,
        )
    command = (settings.github_mcp_command or "").strip()
    if not command:
        return None
    return MCPServerStdio(
        command=command,
        args=_parse_args(settings.github_mcp_args),
        env={
            "GITHUB_PERSONAL_ACCESS_TOKEN": token,
            "GITHUB_TOKEN": token,
        },
        cache_tools_list=settings.mcp_cache_tools_list,
    )


def _resolve_linear_mcp(token: str | None) -> MCPServerConfig | None:
    if not token:
        return None
    if settings.mcp_prefer_remote and settings.linear_mcp_url:
        return MCPServerHTTP(
            url=settings.linear_mcp_url,
            headers=_auth_headers(token),
            streamable=True,
            cache_tools_list=settings.mcp_cache_tools_list,
        )
    command = (settings.linear_mcp_command or "").strip()
    if not command:
        return None
    return MCPServerStdio(
        command=command,
        args=_parse_args(settings.linear_mcp_args),
        env={"LINEAR_API_KEY": token},
        cache_tools_list=settings.mcp_cache_tools_list,
    )


def _resolve_custom_server(server) -> MCPServerConfig | None:
    if server.transport == "http":
        return MCPServerHTTP(
            url=server.command_or_url,
            streamable=True,
            cache_tools_list=settings.mcp_cache_tools_list,
        )
    if server.transport == "sse":
        return MCPServerSSE(
            url=server.command_or_url,
            cache_tools_list=settings.mcp_cache_tools_list,
        )
    if server.transport == "stdio":
        if not settings.mcp_allow_custom_stdio:
            return None
        command, args = _split_command(server.command_or_url)
        if not command:
            return None
        return MCPServerStdio(
            command=command,
            args=args,
            cache_tools_list=settings.mcp_cache_tools_list,
        )
    return None


def resolve_agent_mcps(
    connector_settings: ProjectConnectorSettings | None = None,
    user_id: str | None = None,
) -> list[MCPServerConfig]:
    """Resolve project connector settings into CrewAI MCP server configs.

    GitHub and Linear are enabled by default. Live MCP tools are only attached
    when the authenticated user has saved credentials through the Connectors UI
    (env vars remain a local-dev fallback only).
    """
    connector_settings = connector_settings or ProjectConnectorSettings()
    mcps: list[MCPServerConfig] = []

    if _default_enabled(connector_settings, "github"):
        github = _resolve_github_mcp(resolve_mcp_api_key(user_id, "github"))
        if github is not None:
            mcps.append(github)

    if _default_enabled(connector_settings, "linear"):
        linear = _resolve_linear_mcp(resolve_mcp_api_key(user_id, "linear"))
        if linear is not None:
            mcps.append(linear)

    for server in connector_settings.custom_mcp_servers:
        resolved = _resolve_custom_server(server)
        if resolved is not None:
            mcps.append(resolved)
    return mcps


def get_connector_context(
    connector_settings: ProjectConnectorSettings,
    user_id: str | None = None,
) -> str:
    """Build sanitized connector notes for prompts.

    Returns empty string when nothing is connected and no custom servers are
    attached, so unconfigured production builds do not inject noise. Credentials
    come from the Connectors UI (encrypted per-user settings).
    """
    default_rows: list[str] = []
    for key in DEFAULT_MCP_KEYS:
        enabled = _default_enabled(connector_settings, key)
        if not enabled:
            default_rows.append(
                f"- {_DEFAULT_LABELS[key]} (default)\n"
                f"  Status: disabled"
            )
            continue
        definition = get_mcp_connector(key)
        token = resolve_mcp_api_key(user_id, key)
        if not token and not connector_settings.custom_mcp_servers:
            # Skip unconnected defaults unless the project also has custom MCPs.
            continue
        credential = "connected via UI" if token else "not connected — add a token in Connectors"
        endpoint = definition.default_url if settings.mcp_prefer_remote else (
            f"{settings.github_mcp_command} {settings.github_mcp_args}".strip()
            if key == "github"
            else f"{settings.linear_mcp_command} {settings.linear_mcp_args}".strip()
        )
        default_rows.append(
            f"- {_DEFAULT_LABELS[key]} (default)\n"
            f"  Status: enabled\n"
            f"  Auth: {credential}\n"
            f"  Endpoint: {endpoint}"
        )

    custom_rows: list[str] = []
    for server in connector_settings.custom_mcp_servers:
        if server.transport == "stdio" and not settings.mcp_allow_custom_stdio:
            endpoint = "STDIO command saved as metadata only; not executed."
        elif server.transport == "stdio":
            endpoint = "STDIO process allowed by server policy."
        else:
            endpoint = _safe_remote_url(server.command_or_url)
        notes = f"\n  Notes: {server.notes}" if server.notes else ""
        custom_rows.append(
            f"- {server.name}\n"
            f"  Transport: {server.transport}\n"
            f"  Endpoint: {endpoint}{notes}"
        )

    if not default_rows and not custom_rows:
        return ""

    parts = [
        "--- Connected tool context ---",
        "GitHub and Linear are enabled by default when credentials are saved in Connectors.",
        "Agents receive live MCP tools only after credentials are saved in the UI.",
        "Custom STDIO commands remain metadata-only unless the server allows them.",
        *default_rows,
        *custom_rows,
    ]
    return "\n\n" + "\n".join(parts)


class ConnectorContextInput(BaseModel):
    reason: str = Field(default="", description="Optional reason for reading connector context")


class ConnectorContextTool(BaseTool):
    name: str = "read_connector_context"
    description: str = "Read sanitized MCP connector configuration context attached to this project."
    args_schema: Type[BaseModel] = ConnectorContextInput
    connector_settings: ProjectConnectorSettings = Field(default_factory=ProjectConnectorSettings)
    user_id: str | None = None

    def _run(self, reason: str = "") -> str:
        _ = reason
        context = get_connector_context(self.connector_settings, user_id=self.user_id)
        return context.strip() or "No connector context is attached to this project."
