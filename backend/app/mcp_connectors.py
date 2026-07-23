from dataclasses import dataclass

from app.models import DefaultMcpKey


@dataclass(frozen=True)
class McpConnectorDefinition:
    key: DefaultMcpKey
    label: str
    description: str
    docs_url: str
    connection_url: str
    default_url: str
    env_key: str
    enabled_by_default: bool = True


MCP_CONNECTORS: dict[DefaultMcpKey, McpConnectorDefinition] = {
    "github": McpConnectorDefinition(
        key="github",
        label="GitHub",
        description="Repositories, issues, pull requests, and code context through the official GitHub MCP server.",
        docs_url="https://docs.github.com/en/copilot/how-tos/provide-context/use-mcp/set-up-the-github-mcp-server",
        connection_url="https://github.com/settings/tokens",
        default_url="https://api.githubcopilot.com/mcp/",
        env_key="GITHUB_TOKEN",
    ),
    "linear": McpConnectorDefinition(
        key="linear",
        label="Linear",
        description="Issues, projects, teams, and workflow context through the official Linear MCP server.",
        docs_url="https://linear.app/docs/mcp",
        connection_url="https://linear.app/settings/api",
        default_url="https://mcp.linear.app/mcp",
        env_key="LINEAR_API_KEY",
    ),
}


def get_mcp_connector(key: DefaultMcpKey) -> McpConnectorDefinition:
    return MCP_CONNECTORS[key]
