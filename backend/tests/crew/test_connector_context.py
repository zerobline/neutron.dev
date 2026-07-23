from typing import Literal

from crewai.mcp import MCPServerHTTP, MCPServerSSE, MCPServerStdio

from app.crew.connectors import (
    ConnectorContextTool,
    get_connector_context,
    load_project_connectors,
    merge_connector_settings,
    resolve_agent_mcps,
    save_project_connectors,
)
from app.models import CustomMcpServerConfig, DefaultMcpConfig, ProjectConnectorSettings

CustomTransport = Literal["stdio", "sse", "http"]


def make_settings(
    server_id: str = "remote",
    command_or_url: str = "https://example.com/mcp",
    transport: CustomTransport = "http",
):
    return ProjectConnectorSettings(
        custom_mcp_servers=[
            CustomMcpServerConfig(
                id=server_id,
                name="Remote MCP",
                transport=transport,
                command_or_url=command_or_url,
                notes="Use for specs",
            )
        ]
    )


def test_load_project_connectors_missing_file():
    settings = load_project_connectors("missing")
    assert settings.custom_mcp_servers == []
    assert [item.key for item in settings.default_mcps] == ["github", "linear"]
    assert all(item.enabled for item in settings.default_mcps)


def test_save_and_load_project_connectors_roundtrip():
    saved = save_project_connectors("p1", make_settings())
    loaded = load_project_connectors("p1")
    assert loaded == saved
    assert loaded.custom_mcp_servers[0].command_or_url == "https://example.com/mcp"
    assert [item.key for item in loaded.default_mcps] == ["github", "linear"]


def test_load_project_connectors_ignores_invalid_json(settings_projects_dir):
    project_dir = settings_projects_dir / "p1"
    project_dir.mkdir()
    (project_dir / "connectors.json").write_text("not-json", encoding="utf-8")
    assert load_project_connectors("p1").custom_mcp_servers == []


def test_merge_connector_settings_overrides_by_id():
    saved = make_settings(server_id="same", command_or_url="https://old.example/mcp")
    inline = make_settings(server_id="same", command_or_url="https://new.example/mcp")
    merged = merge_connector_settings(saved, inline)
    assert len(merged.custom_mcp_servers) == 1
    assert merged.custom_mcp_servers[0].command_or_url == "https://new.example/mcp"


def test_merge_connector_settings_accepts_dict_and_none():
    saved = make_settings()
    assert merge_connector_settings(saved, None) is saved
    merged = merge_connector_settings(saved, {"custom_mcp_servers": []})
    assert merged.custom_mcp_servers == saved.custom_mcp_servers
    assert [item.key for item in merged.default_mcps] == ["github", "linear"]


def test_merge_connector_settings_overrides_default_enabled():
    saved = ProjectConnectorSettings()
    inline = ProjectConnectorSettings(
        default_mcps=[
            DefaultMcpConfig(key="github", enabled=False),
            DefaultMcpConfig(key="linear", enabled=True),
        ]
    )
    merged = merge_connector_settings(saved, inline)
    assert merged.default_mcps[0].enabled is False
    assert merged.default_mcps[1].enabled is True


def test_connector_context_includes_defaults_and_sanitizes_remote_url(monkeypatch):
    def _token_for_github(*args):
        return "token" if args[1] == "github" else None

    monkeypatch.setattr("app.crew.connectors.resolve_mcp_api_key", _token_for_github)
    connector_settings = ProjectConnectorSettings(
        custom_mcp_servers=[
            CustomMcpServerConfig(
                id="remote",
                name="Remote MCP",
                transport="sse",
                command_or_url="https://example.com:8443/mcp?token=secret#frag",
                notes="Remote notes",
            ),
            CustomMcpServerConfig(
                id="stdio",
                name="Filesystem",
                transport="stdio",
                command_or_url="npx -y @modelcontextprotocol/server-filesystem .",
                notes="Local files",
            ),
        ]
    )
    context = get_connector_context(connector_settings, user_id="user-1")
    assert "GitHub (default)" in context
    assert "Linear (default)" in context
    assert "connected via UI" in context
    assert "not connected" in context
    assert "https://example.com:8443/mcp" in context
    assert "token=secret" not in context
    assert "STDIO command saved as metadata only; not executed." in context
    assert "npx -y" not in context


def test_connector_context_empty_when_unconnected_and_no_custom_servers(monkeypatch):
    monkeypatch.setattr("app.crew.connectors.resolve_mcp_api_key", lambda *args: None)
    assert get_connector_context(ProjectConnectorSettings()) == ""


def test_connector_context_shows_connected_defaults_without_custom_servers(monkeypatch):
    def _token_for_github(*args):
        return "token" if args[1] == "github" else None

    monkeypatch.setattr("app.crew.connectors.resolve_mcp_api_key", _token_for_github)
    context = get_connector_context(ProjectConnectorSettings(), user_id="user-1")
    assert "GitHub (default)" in context
    assert "connected via UI" in context
    assert "Linear (default)" not in context


def test_connector_context_tool_returns_context_or_empty_message(monkeypatch):
    monkeypatch.setattr("app.crew.connectors.resolve_mcp_api_key", lambda *args: None)
    tool = ConnectorContextTool(connector_settings=make_settings(), user_id="user-1")
    assert "Remote MCP" in tool._run(reason="need context")

    empty_tool = ConnectorContextTool()
    assert empty_tool._run() == "No connector context is attached to this project."


def test_resolve_agent_mcps_requires_ui_credentials(monkeypatch):
    monkeypatch.setattr("app.crew.connectors.resolve_mcp_api_key", lambda *args: None)
    assert resolve_agent_mcps(ProjectConnectorSettings(), user_id="user-1") == []


def test_resolve_agent_mcps_attaches_github_and_linear(monkeypatch):
    def _tokens(*args):
        return "gh-token" if args[1] == "github" else "lin-token"

    monkeypatch.setattr("app.crew.connectors.resolve_mcp_api_key", _tokens)
    monkeypatch.setattr("app.crew.connectors.settings.mcp_prefer_remote", True)
    mcps = resolve_agent_mcps(ProjectConnectorSettings(), user_id="user-1")
    assert len(mcps) == 2
    assert all(isinstance(mcp, MCPServerHTTP) for mcp in mcps)
    github, linear = mcps
    assert isinstance(github, MCPServerHTTP)
    assert isinstance(linear, MCPServerHTTP)
    assert github.url.endswith("/mcp/") or "github" in github.url
    assert github.headers == {"Authorization": "Bearer gh-token"}
    assert linear.headers == {"Authorization": "Bearer lin-token"}


def test_resolve_agent_mcps_skips_disabled_defaults_and_resolves_custom(monkeypatch):
    monkeypatch.setattr("app.crew.connectors.resolve_mcp_api_key", lambda *args: "token")
    monkeypatch.setattr("app.crew.connectors.settings.mcp_prefer_remote", True)
    monkeypatch.setattr("app.crew.connectors.settings.mcp_allow_custom_stdio", False)
    connector_settings = ProjectConnectorSettings(
        default_mcps=[
            DefaultMcpConfig(key="github", enabled=False),
            DefaultMcpConfig(key="linear", enabled=True),
        ],
        custom_mcp_servers=[
            CustomMcpServerConfig(
                id="remote",
                name="Remote",
                transport="http",
                command_or_url="https://example.com/mcp",
            ),
            CustomMcpServerConfig(
                id="stream",
                name="Stream",
                transport="sse",
                command_or_url="https://example.com/sse",
            ),
            CustomMcpServerConfig(
                id="local",
                name="Local",
                transport="stdio",
                command_or_url="npx -y demo",
            ),
        ],
    )
    mcps = resolve_agent_mcps(connector_settings, user_id="user-1")
    assert len(mcps) == 3
    assert isinstance(mcps[0], MCPServerHTTP)
    assert isinstance(mcps[1], MCPServerHTTP)
    assert mcps[1].url == "https://example.com/mcp"
    assert isinstance(mcps[2], MCPServerSSE)


def test_resolve_agent_mcps_stdio_fallback_and_custom_stdio(monkeypatch):
    monkeypatch.setattr("app.crew.connectors.resolve_mcp_api_key", lambda *args: "token")
    monkeypatch.setattr("app.crew.connectors.settings.mcp_prefer_remote", False)
    monkeypatch.setattr("app.crew.connectors.settings.mcp_allow_custom_stdio", True)
    connector_settings = ProjectConnectorSettings(
        custom_mcp_servers=[
            CustomMcpServerConfig(
                id="local",
                name="Local",
                transport="stdio",
                command_or_url="npx -y demo server",
            )
        ]
    )
    mcps = resolve_agent_mcps(connector_settings, user_id="user-1")
    assert len(mcps) == 3
    assert all(isinstance(mcp, MCPServerStdio) for mcp in mcps)
    custom = mcps[2]
    assert isinstance(custom, MCPServerStdio)
    assert custom.command == "npx"
    assert custom.args == ["-y", "demo", "server"]


def test_resolve_agent_mcps_skips_empty_commands_and_disabled_defaults(monkeypatch):
    monkeypatch.setattr(
        "app.crew.connectors.resolve_mcp_api_key",
        lambda *args: "token" if args[1] == "linear" else None,
    )
    monkeypatch.setattr("app.crew.connectors.settings.mcp_prefer_remote", False)
    monkeypatch.setattr("app.crew.connectors.settings.github_mcp_command", " ")
    monkeypatch.setattr("app.crew.connectors.settings.linear_mcp_command", "npx")
    monkeypatch.setattr("app.crew.connectors.settings.linear_mcp_args", "")
    monkeypatch.setattr("app.crew.connectors.settings.mcp_allow_custom_stdio", True)
    # Model validation rejects blank command_or_url; force empty split at resolve time.
    monkeypatch.setattr("app.crew.connectors._split_command", lambda value: ("", []))
    connector_settings = ProjectConnectorSettings(
        default_mcps=[
            DefaultMcpConfig(key="github", enabled=True),
            DefaultMcpConfig(key="linear", enabled=True),
        ],
        custom_mcp_servers=[
            CustomMcpServerConfig(
                id="blank",
                name="Blank",
                transport="stdio",
                command_or_url="npx demo",
            )
        ],
    )
    mcps = resolve_agent_mcps(connector_settings, user_id="user-1")
    assert len(mcps) == 1
    assert isinstance(mcps[0], MCPServerStdio)


def test_resolve_agent_mcps_skips_linear_without_stdio_command(monkeypatch):
    monkeypatch.setattr("app.crew.connectors.resolve_mcp_api_key", lambda *args: "token")
    monkeypatch.setattr("app.crew.connectors.settings.mcp_prefer_remote", False)
    monkeypatch.setattr("app.crew.connectors.settings.github_mcp_command", "npx")
    monkeypatch.setattr("app.crew.connectors.settings.linear_mcp_command", " ")
    mcps = resolve_agent_mcps(ProjectConnectorSettings(), user_id="user-1")
    assert len(mcps) == 1
    assert isinstance(mcps[0], MCPServerStdio)


def test_resolve_agent_mcps_skips_github_without_stdio_command(monkeypatch):
    monkeypatch.setattr("app.crew.connectors.resolve_mcp_api_key", lambda *args: "token")
    monkeypatch.setattr("app.crew.connectors.settings.mcp_prefer_remote", False)
    monkeypatch.setattr("app.crew.connectors.settings.github_mcp_command", " ")
    monkeypatch.setattr("app.crew.connectors.settings.linear_mcp_command", "npx")
    mcps = resolve_agent_mcps(ProjectConnectorSettings(), user_id="user-1")
    assert len(mcps) == 1
    assert isinstance(mcps[0], MCPServerStdio)


def test_resolve_agent_mcps_skips_disabled_linear(monkeypatch):
    monkeypatch.setattr(
        "app.crew.connectors.resolve_mcp_api_key",
        lambda *args: "token" if args[1] == "github" else None,
    )
    monkeypatch.setattr("app.crew.connectors.settings.mcp_prefer_remote", True)
    connector_settings = ProjectConnectorSettings(
        default_mcps=[
            DefaultMcpConfig(key="github", enabled=True),
            DefaultMcpConfig(key="linear", enabled=False),
        ]
    )
    mcps = resolve_agent_mcps(connector_settings, user_id="user-1")
    assert len(mcps) == 1
    assert isinstance(mcps[0], MCPServerHTTP)


def test_helper_edge_cases_and_unknown_transport():
    from app.crew.connectors import _auth_headers, _default_enabled, _parse_args, _resolve_custom_server, _split_command

    assert _split_command("") == ("", [])
    assert _parse_args("") == []
    assert _parse_args(None) == []  # type: ignore[arg-type]
    assert _auth_headers(None) is None
    assert _auth_headers("tok") == {"Authorization": "Bearer tok"}

    empty_defaults = ProjectConnectorSettings.model_construct(default_mcps=[], custom_mcp_servers=[])
    assert _default_enabled(empty_defaults, "github") is True
    assert _default_enabled(empty_defaults, "other") is False

    class Unknown:
        transport = "ftp"
        command_or_url = "ftp://example.com"

    assert _resolve_custom_server(Unknown()) is None


def test_connector_context_marks_disabled_defaults(monkeypatch):
    monkeypatch.setattr("app.crew.connectors.resolve_mcp_api_key", lambda *args: None)
    connector_settings = ProjectConnectorSettings(
        default_mcps=[
            DefaultMcpConfig(key="github", enabled=False),
            DefaultMcpConfig(key="linear", enabled=False),
        ],
        custom_mcp_servers=[
            CustomMcpServerConfig(
                id="remote",
                name="Remote",
                transport="http",
                command_or_url="https://example.com/mcp",
                notes="",
            )
        ],
    )
    context = get_connector_context(connector_settings)
    assert "Status: disabled" in context
    assert "Remote" in context


def test_connector_context_allows_stdio_when_server_policy_enabled(monkeypatch):
    monkeypatch.setattr("app.crew.connectors.resolve_mcp_api_key", lambda *args: None)
    monkeypatch.setattr("app.crew.connectors.settings.mcp_allow_custom_stdio", True)
    connector_settings = ProjectConnectorSettings(
        custom_mcp_servers=[
            CustomMcpServerConfig(
                id="local",
                name="Local",
                transport="stdio",
                command_or_url="npx demo",
                notes="",
            )
        ]
    )
    context = get_connector_context(connector_settings)
    assert "STDIO process allowed by server policy." in context


def test_project_connector_settings_dedupes_and_fills_defaults():
    settings = ProjectConnectorSettings(
        default_mcps=[
            DefaultMcpConfig(key="github", enabled=False),
            DefaultMcpConfig(key="github", enabled=True),
        ]
    )
    assert [item.key for item in settings.default_mcps] == ["github", "linear"]
    assert settings.default_mcps[0].enabled is False
    assert settings.default_mcps[1].enabled is True
