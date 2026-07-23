import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ConnectorsModal } from "@/components/dashboard/connectors-modal";

const removedConnectors = ["Dropbox", "MCP Server", "Google Analytics 4"];

const listMcpConnectorSettings = vi.fn();
const updateMcpConnectorSettings = vi.fn();
const clearMcpConnectorKey = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    listMcpConnectorSettings: (...args: unknown[]) => listMcpConnectorSettings(...args),
    updateMcpConnectorSettings: (...args: unknown[]) => updateMcpConnectorSettings(...args),
    clearMcpConnectorKey: (...args: unknown[]) => clearMcpConnectorKey(...args),
  },
}));

const defaultConnectors = {
  connectors: [
    {
      key: "github",
      label: "GitHub",
      description: "GitHub MCP",
      docs_url: "https://docs.github.com/en/copilot/how-tos/provide-context/use-mcp/set-up-the-github-mcp-server",
      connection_url: "https://github.com/settings/tokens",
      default_url: "https://api.githubcopilot.com/mcp/",
      has_api_key: false,
      has_user_api_key: false,
      enabled_by_default: true,
    },
    {
      key: "linear",
      label: "Linear",
      description: "Linear MCP",
      docs_url: "https://linear.app/docs/mcp",
      connection_url: "https://linear.app/settings/api",
      default_url: "https://mcp.linear.app/mcp",
      has_api_key: false,
      has_user_api_key: false,
      enabled_by_default: true,
    },
  ],
};

describe("ConnectorsModal", () => {
  beforeEach(() => {
    listMcpConnectorSettings.mockReset();
    updateMcpConnectorSettings.mockReset();
    clearMcpConnectorKey.mockReset();
    listMcpConnectorSettings.mockResolvedValue(defaultConnectors);
  });

  it("does not render when closed", () => {
    render(<ConnectorsModal open={false} onClose={vi.fn()} />);
    expect(screen.queryByText("Connectors")).not.toBeInTheDocument();
  });

  it("renders hosted GitHub, Linear, and Supabase MCP connectors when open", async () => {
    render(<ConnectorsModal open onClose={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "Connectors" })).toBeInTheDocument();
    await waitFor(() => expect(listMcpConnectorSettings).toHaveBeenCalled());
    expect(screen.getAllByText("GitHub").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Linear").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Supabase").length).toBeGreaterThan(0);
    removedConnectors.forEach((name) => expect(screen.queryByText(name)).not.toBeInTheDocument());
    expect(screen.getAllByText("Default MCP").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("No custom MCP servers yet.")).toBeInTheDocument();
  });

  it("filters hosted and custom connectors by search query", async () => {
    const user = userEvent.setup();
    localStorage.setItem("neutron-custom-mcp-servers", JSON.stringify([
      { id: "fs", name: "Filesystem", transport: "stdio", commandOrUrl: "npx filesystem", notes: "local", createdAt: "2026-01-01", updatedAt: "2026-01-01" },
    ]));
    render(<ConnectorsModal open onClose={vi.fn()} />);
    await waitFor(() => expect(listMcpConnectorSettings).toHaveBeenCalled());
    await user.type(screen.getByPlaceholderText("Search optional connectors"), "Git");
    expect(screen.getAllByText("GitHub").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /Linear/ })).not.toBeInTheDocument();
    expect(screen.getByText("No custom MCP servers match your search.")).toBeInTheDocument();

    await user.clear(screen.getByPlaceholderText("Search optional connectors"));
    await user.type(screen.getByPlaceholderText("Search optional connectors"), "filesystem");
    expect(screen.queryByRole("button", { name: /GitHub/ })).not.toBeInTheDocument();
    expect(screen.getByText("Filesystem")).toBeInTheDocument();
  });

  it("shows token actions for the selected connector", async () => {
    const user = userEvent.setup();
    render(<ConnectorsModal open onClose={vi.fn()} />);
    await waitFor(() => expect(listMcpConnectorSettings).toHaveBeenCalled());
    expect(screen.getByRole("link", { name: "Get GitHub token" })).toHaveAttribute("href", "https://github.com/settings/tokens");
    expect(screen.getByRole("link", { name: "View setup guide" })).toHaveAttribute(
      "href",
      "https://docs.github.com/en/copilot/how-tos/provide-context/use-mcp/set-up-the-github-mcp-server"
    );

    await user.click(screen.getByRole("button", { name: /Linear/ }));
    expect(screen.getByRole("link", { name: "Get Linear token" })).toHaveAttribute("href", "https://linear.app/settings/api");
    expect(screen.getByRole("link", { name: "View setup guide" })).toHaveAttribute("href", "https://linear.app/docs/mcp");

    await user.click(screen.getByRole("button", { name: /Supabase/ }));
    expect(screen.getByRole("link", { name: "Get Supabase token" })).toHaveAttribute("href", "https://supabase.com/dashboard/account/tokens");
    expect(screen.getByRole("link", { name: "View setup guide" })).toHaveAttribute("href", "https://supabase.com/docs/guides/getting-started/mcp");
    expect(localStorage.getItem("neutron-local-connectors")).toBeNull();
  });

  it("saves a default MCP credential from the UI form", async () => {
    const user = userEvent.setup({ delay: null });
    updateMcpConnectorSettings.mockResolvedValue({
      ...defaultConnectors.connectors[0],
      has_api_key: true,
      has_user_api_key: true,
    });
    render(<ConnectorsModal open onClose={vi.fn()} />);
    await waitFor(() => expect(listMcpConnectorSettings).toHaveBeenCalled());

    await user.type(screen.getAllByPlaceholderText("ghp_... personal access token")[0], "ghp_test_token");
    await user.click(screen.getAllByRole("button", { name: "Save" })[0]);

    await waitFor(() => expect(updateMcpConnectorSettings).toHaveBeenCalledWith({
      key: "github",
      api_key: "ghp_test_token",
    }));
    expect(await screen.findByText("GitHub credential saved. Agents will use it on the next build.")).toBeInTheDocument();
  }, 30_000);

  it("requires a token before saving default MCP credentials", async () => {
    const user = userEvent.setup({ delay: null });
    render(<ConnectorsModal open onClose={vi.fn()} />);
    await waitFor(() => expect(listMcpConnectorSettings).toHaveBeenCalled());
    await user.click(screen.getAllByRole("button", { name: "Save" })[0]);
    expect(await screen.findByText("Paste a GitHub token before saving.")).toBeInTheDocument();
    expect(updateMcpConnectorSettings).not.toHaveBeenCalled();
  });

  it("handles default MCP save failures", async () => {
    const user = userEvent.setup({ delay: null });
    updateMcpConnectorSettings.mockRejectedValueOnce(new Error("save failed"));
    render(<ConnectorsModal open onClose={vi.fn()} />);
    await waitFor(() => expect(listMcpConnectorSettings).toHaveBeenCalled());
    await user.type(screen.getAllByPlaceholderText("ghp_... personal access token")[0], "ghp_bad");
    await user.click(screen.getAllByRole("button", { name: "Save" })[0]);
    expect(await screen.findByText("Could not save the GitHub credential.")).toBeInTheDocument();
  });

  it("removes a connected default MCP credential", async () => {
    const user = userEvent.setup({ delay: null });
    listMcpConnectorSettings.mockResolvedValue({
      connectors: [
        {
          ...defaultConnectors.connectors[0],
          has_api_key: true,
          has_user_api_key: true,
        },
        defaultConnectors.connectors[1],
      ],
    });
    clearMcpConnectorKey.mockResolvedValue({
      ...defaultConnectors.connectors[0],
      has_api_key: false,
      has_user_api_key: false,
    });
    render(<ConnectorsModal open onClose={vi.fn()} />);
    await waitFor(() => expect(listMcpConnectorSettings).toHaveBeenCalled());
    const removeButtons = screen.getAllByRole("button", { name: "Remove" });
    expect(removeButtons[0]).not.toBeDisabled();
    await user.click(removeButtons[0]);
    await waitFor(() => expect(clearMcpConnectorKey).toHaveBeenCalledWith("github"));
    expect(await screen.findByText("GitHub credential removed.")).toBeInTheDocument();
  });

  it("reports when a removed MCP key still has a server default", async () => {
    const user = userEvent.setup({ delay: null });
    listMcpConnectorSettings.mockResolvedValue({
      connectors: [
        {
          ...defaultConnectors.connectors[0],
          has_api_key: true,
          has_user_api_key: true,
        },
        defaultConnectors.connectors[1],
      ],
    });
    clearMcpConnectorKey.mockResolvedValue({
      ...defaultConnectors.connectors[0],
      has_api_key: true,
      has_user_api_key: false,
    });
    render(<ConnectorsModal open onClose={vi.fn()} />);
    await waitFor(() => expect(listMcpConnectorSettings).toHaveBeenCalled());
    await user.click(screen.getAllByRole("button", { name: "Remove" })[0]);
    expect(
      await screen.findByText("GitHub key removed. A server default is still available."),
    ).toBeInTheDocument();
  });

  it("handles default MCP remove failures", async () => {
    const user = userEvent.setup({ delay: null });
    listMcpConnectorSettings.mockResolvedValue({
      connectors: [
        {
          ...defaultConnectors.connectors[0],
          has_api_key: true,
          has_user_api_key: true,
        },
        defaultConnectors.connectors[1],
      ],
    });
    clearMcpConnectorKey.mockRejectedValueOnce(new Error("clear failed"));
    render(<ConnectorsModal open onClose={vi.fn()} />);
    await waitFor(() => expect(listMcpConnectorSettings).toHaveBeenCalled());
    await user.click(screen.getAllByRole("button", { name: "Remove" })[0]);
    expect(await screen.findByText("Could not remove the GitHub credential.")).toBeInTheDocument();
  });

  it("shows load errors for default MCP connectors", async () => {
    listMcpConnectorSettings.mockRejectedValueOnce(new Error("load failed"));
    render(<ConnectorsModal open onClose={vi.fn()} />);
    expect(
      await screen.findByText("Could not load MCP connectors. Log in and try again."),
    ).toBeInTheDocument();
  });

  it("supports compact default MCP panel layout", async () => {
    const { DefaultMcpConnectorsPanel } = await import(
      "@/components/connectors/default-mcp-connectors-panel"
    );
    render(<DefaultMcpConnectorsPanel compact />);
    await waitFor(() => expect(listMcpConnectorSettings).toHaveBeenCalled());
    expect(screen.getByText("Default MCP connectors")).toBeInTheDocument();
  });

  it("adds a stdio custom MCP server locally", async () => {
    const user = userEvent.setup({ delay: null });
    render(<ConnectorsModal open onClose={vi.fn()} />);
    await waitFor(() => expect(listMcpConnectorSettings).toHaveBeenCalled());

    await user.click(screen.getByRole("button", { name: /Add custom server/ }));
    await user.type(screen.getByLabelText("Name"), "Filesystem");
    await user.type(screen.getByLabelText("Command or URL"), "npx -y @modelcontextprotocol/server-filesystem .");
    await user.type(screen.getByLabelText("Notes"), "Local project files");
    await user.click(screen.getByRole("button", { name: "Save custom server" }));

    expect(await screen.findByText("Custom MCP server saved locally.")).toBeInTheDocument();
    expect(screen.getAllByText("Filesystem").length).toBeGreaterThan(0);
    expect(screen.getByText("npx -y @modelcontextprotocol/server-filesystem .")).toBeInTheDocument();
    expect(localStorage.getItem("neutron-custom-mcp-servers")).toContain("Filesystem");
  }, 30_000);

  it("validates and saves remote custom MCP server URLs", async () => {
    const user = userEvent.setup({ delay: null });
    render(<ConnectorsModal open onClose={vi.fn()} />);
    await waitFor(() => expect(listMcpConnectorSettings).toHaveBeenCalled());

    await user.click(screen.getByRole("button", { name: /Add custom server/ }));
    await user.type(screen.getByLabelText("Name"), "Remote MCP");
    await user.selectOptions(screen.getByLabelText("Transport"), "http");
    await user.type(screen.getByLabelText("Command or URL"), "example.com/mcp");
    expect(screen.getByText("Remote MCP servers must start with http:// or https://.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save custom server" })).toBeDisabled();

    await user.clear(screen.getByLabelText("Command or URL"));
    await user.type(screen.getByLabelText("Command or URL"), "https://example.com/mcp");
    await user.click(screen.getByRole("button", { name: "Save custom server" }));
    expect(await screen.findByText("Remote MCP")).toBeInTheDocument();
    expect(localStorage.getItem("neutron-custom-mcp-servers")).toContain("https://example.com/mcp");
  }, 30_000);

  it("edits and deletes a custom MCP server", async () => {
    const user = userEvent.setup();
    localStorage.setItem("neutron-custom-mcp-servers", JSON.stringify([
      { id: "fs", name: "Filesystem", transport: "stdio", commandOrUrl: "npx filesystem", notes: "local", createdAt: "2026-01-01", updatedAt: "2026-01-01" },
    ]));
    render(<ConnectorsModal open onClose={vi.fn()} />);
    await waitFor(() => expect(listMcpConnectorSettings).toHaveBeenCalled());

    await user.click(screen.getByRole("button", { name: "Edit" }));
    await user.clear(screen.getByLabelText("Name"));
    await user.type(screen.getByLabelText("Name"), "Filesystem MCP");
    await user.click(screen.getByRole("button", { name: "Update custom server" }));
    expect(screen.getByText("Custom MCP server updated.")).toBeInTheDocument();
    expect(localStorage.getItem("neutron-custom-mcp-servers")).toContain("Filesystem MCP");

    await user.click(screen.getByRole("button", { name: /Delete/ }));
    expect(screen.getByText("Custom MCP server deleted.")).toBeInTheDocument();
    expect(screen.queryByText("Filesystem MCP")).not.toBeInTheDocument();
    expect(localStorage.getItem("neutron-custom-mcp-servers")).not.toContain("Filesystem MCP");
  });

  it("calls onClose when close button is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<ConnectorsModal open onClose={onClose} />);
    await waitFor(() => expect(listMcpConnectorSettings).toHaveBeenCalled());
    await user.click(screen.getByRole("button", { name: "Close connectors" }));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
