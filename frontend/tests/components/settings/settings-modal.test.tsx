import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SettingsModal } from "@/components/settings/settings-modal";
import { api, type LlmProvider, type ProviderSummary } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";

const oauthConnectedMessage =
  /Grok OAuth connected( and activated for builds)?\. SuperGrok or X Premium\+ subscription required\./;

vi.mock("@/lib/api", () => ({
  api: {
    getAvailableModels: vi.fn().mockResolvedValue({
      models: [
        { value: "openai/gpt-4o", label: "OpenAI GPT-4o" },
        { value: "anthropic/claude-sonnet-4-20250514", label: "Claude Sonnet" },
      ],
      current: "openai/gpt-4o",
    }),
    getAgentModels: vi.fn().mockResolvedValue({
      provider: "openai-compatible",
      default_model: "kimchi/kimi-k2.7",
      agents: [],
    }),
    updateAgentModels: vi.fn().mockResolvedValue({
      provider: "openai-compatible",
      default_model: "kimchi/kimi-k2.7",
      agents: [],
    }),
    getProviderSettings: vi.fn().mockResolvedValue({
      provider: "openai-compatible",
      model: "kimchi/kimi-k2.7",
      base_url: "http://localhost:20128/v1",
      has_api_key: false,
      effective_model: "openai/kimchi/kimi-k2.7",
    }),
    getProviderModels: vi.fn().mockImplementation((provider: LlmProvider) => {
      const catalogs: Partial<Record<LlmProvider, Array<{ value: string; label: string }>>> = {
        openai: [{ value: "gpt-4o", label: "gpt 4o" }],
        openrouter: [{ value: "openai/gpt-4o-mini", label: "openai / gpt 4o mini" }],
        kimi: [{ value: "kimi-for-coding", label: "kimi for coding" }],
        "openai-compatible": [{ value: "kimchi/kimi-k2.7", label: "kimchi / kimi k2.7" }],
        groq: [{ value: "llama-3.3-70b-versatile", label: "llama 3.3 70b versatile" }],
      };
      const models = catalogs[provider] ?? [];
      return Promise.resolve({
        provider,
        models,
        current: models[0]?.value ?? "",
        source: "catalog" as const,
      });
    }),
    listProviderSettings: vi.fn().mockResolvedValue({
      active_provider: "openai-compatible",
      providers: [
        {
          provider: "openai-compatible",
          label: "OpenAI-compatible",
          model: "kimchi/kimi-k2.7",
          base_url: "http://localhost:20128/v1",
          has_api_key: false,
          effective_model: "openai/kimchi/kimi-k2.7",
          is_active: true,
          requires_base_url: true,
          requires_api_key: false,
          auth_method: "api_key",
          is_connected: false,
        },
      ] satisfies ProviderSummary[],
    }),
    updateProviderSettings: vi.fn().mockResolvedValue({
      provider: "openai-compatible",
      model: "kimchi/kimi-k2.7",
      base_url: "http://localhost:20128/v1",
      has_api_key: true,
      effective_model: "openai/kimchi/kimi-k2.7",
    }),
    activateProvider: vi.fn().mockResolvedValue({
      provider: "openai-compatible",
      model: "kimchi/kimi-k2.7",
      base_url: "http://localhost:20128/v1",
      has_api_key: false,
      effective_model: "openai/kimchi/kimi-k2.7",
    }),
    clearProviderKey: vi.fn().mockResolvedValue({
      provider: "openai-compatible",
      model: "kimchi/kimi-k2.7",
      base_url: "http://localhost:20128/v1",
      has_api_key: false,
      effective_model: "openai/kimchi/kimi-k2.7",
    }),
    startXaiOAuth: vi.fn().mockResolvedValue({
      session_id: "session-1",
      verification_uri: "https://auth.x.ai/device",
      user_code: "ABCD-1234",
      expires_in: 600,
      interval: 1,
    }),
    pollXaiOAuth: vi.fn().mockResolvedValue({ status: "pending", interval: 30 }),
    disconnectXaiOAuth: vi.fn().mockResolvedValue({
      provider: "xai-oauth",
      model: "grok-4.5",
      base_url: "https://api.x.ai/v1",
      has_api_key: false,
      effective_model: "xai/grok-4.5",
    }),
    listSearchProviderSettings: vi.fn().mockResolvedValue({ providers: [] }),
    updateSearchProviderSettings: vi.fn(),
    clearSearchProviderKey: vi.fn(),
    listMcpConnectorSettings: vi.fn().mockResolvedValue({
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
    }),
    updateMcpConnectorSettings: vi.fn(),
    clearMcpConnectorKey: vi.fn(),
  },
}));

const removedConnectors = ["Dropbox", "MCP Server", "Google Analytics 4"];

function resetApiMocks() {
  vi.mocked(api.getProviderModels).mockImplementation((provider: LlmProvider) => {
    const catalogs: Partial<Record<LlmProvider, Array<{ value: string; label: string }>>> = {
      openai: [{ value: "gpt-4o", label: "gpt 4o" }],
      openrouter: [{ value: "openai/gpt-4o-mini", label: "openai / gpt 4o mini" }],
      kimi: [{ value: "kimi-for-coding", label: "kimi for coding" }],
      "openai-compatible": [{ value: "kimchi/kimi-k2.7", label: "kimchi / kimi k2.7" }],
      groq: [{ value: "llama-3.3-70b-versatile", label: "llama 3.3 70b versatile" }],
    };
    const models = catalogs[provider] ?? [];
    return Promise.resolve({
      provider,
      models,
      current: models[0]?.value ?? "",
      source: "catalog" as const,
    });
  });
  vi.mocked(api.getAvailableModels).mockResolvedValue({
    models: [
      { value: "openai/gpt-4o", label: "OpenAI GPT-4o" },
      { value: "anthropic/claude-sonnet-4-20250514", label: "Claude Sonnet" },
    ],
    current: "openai/gpt-4o",
  });
  vi.mocked(api.getAgentModels).mockResolvedValue({
    provider: "openai-compatible",
    default_model: "kimchi/kimi-k2.7",
    agents: [],
  });
  vi.mocked(api.updateAgentModels).mockResolvedValue({
    provider: "openai-compatible",
    default_model: "kimchi/kimi-k2.7",
    agents: [],
  });
  vi.mocked(api.getProviderSettings).mockResolvedValue({
    provider: "openai-compatible",
    model: "kimchi/kimi-k2.7",
    base_url: "http://localhost:20128/v1",
    has_api_key: false,
    effective_model: "openai/kimchi/kimi-k2.7",
  });
  vi.mocked(api.listProviderSettings).mockResolvedValue({
    active_provider: "openai-compatible",
    providers: [
      {
        provider: "openai-compatible",
        label: "OpenAI-compatible",
        model: "kimchi/kimi-k2.7",
        base_url: "http://localhost:20128/v1",
        has_api_key: false,
        effective_model: "openai/kimchi/kimi-k2.7",
        is_active: true,
        requires_base_url: true,
        requires_api_key: false,
        auth_method: "api_key",
        is_connected: false,
      },
    ],
  });
  vi.mocked(api.updateProviderSettings).mockResolvedValue({
    provider: "openai-compatible",
    model: "kimchi/kimi-k2.7",
    base_url: "http://localhost:20128/v1",
    has_api_key: true,
    effective_model: "openai/kimchi/kimi-k2.7",
  });
  vi.mocked(api.activateProvider).mockResolvedValue({
    provider: "openai-compatible",
    model: "kimchi/kimi-k2.7",
    base_url: "http://localhost:20128/v1",
    has_api_key: false,
    effective_model: "openai/kimchi/kimi-k2.7",
  });
  vi.mocked(api.clearProviderKey).mockResolvedValue({
    provider: "openai-compatible",
    model: "kimchi/kimi-k2.7",
    base_url: "http://localhost:20128/v1",
    has_api_key: false,
    effective_model: "openai/kimchi/kimi-k2.7",
  });
  vi.mocked(api.startXaiOAuth).mockResolvedValue({
    session_id: "session-1",
    verification_uri: "https://auth.x.ai/device",
    user_code: "ABCD-1234",
    expires_in: 600,
    interval: 1,
  });
  vi.mocked(api.pollXaiOAuth).mockResolvedValue({ status: "pending", interval: 30 });
  vi.mocked(api.disconnectXaiOAuth).mockResolvedValue({
    provider: "xai-oauth",
    model: "grok-4.5",
    base_url: "https://api.x.ai/v1",
    has_api_key: false,
    effective_model: "xai/grok-4.5",
  });
  vi.mocked(api.listSearchProviderSettings).mockResolvedValue({ providers: [] });
  vi.mocked(api.listMcpConnectorSettings).mockResolvedValue({
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
  });
}

describe("SettingsModal", () => {
  beforeEach(() => {
    resetApiMocks();
  });

  it("does not render when closed", () => {
    render(<SettingsModal open={false} onClose={vi.fn()} />);
    expect(screen.queryByText("Settings")).not.toBeInTheDocument();
  });

  it("renders the general section with one authoritative AI setup path", () => {
    render(<SettingsModal open onClose={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "General" })).toBeInTheDocument();
    expect(screen.getByText("AI provider and model")).toBeInTheDocument();
    expect(screen.queryByText("Default Model")).not.toBeInTheDocument();
    expect(screen.getByText("Theme")).toBeInTheDocument();
    expect(screen.getByText("Permissions")).toBeInTheDocument();
  });

  it("navigates to the connectors section", async () => {
    const user = userEvent.setup();
    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Connectors" }));
    expect(screen.getByRole("heading", { name: "Connectors" })).toBeInTheDocument();
    await waitFor(() => expect(api.listMcpConnectorSettings).toHaveBeenCalled());
    expect(screen.getAllByText("GitHub").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Linear").length).toBeGreaterThan(0);
    expect(screen.getByText("Supabase")).toBeInTheDocument();
    expect(screen.getAllByText("Default MCP").length).toBeGreaterThanOrEqual(2);
    removedConnectors.forEach((name) => expect(screen.queryByText(name)).not.toBeInTheDocument());
  });

  it("navigates to search API credentials", async () => {
    const user = userEvent.setup();
    render(<SettingsModal open onClose={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Search APIs" }));

    expect(screen.getByRole("heading", { name: "Search APIs" })).toBeInTheDocument();
    await waitFor(() => expect(api.listSearchProviderSettings).toHaveBeenCalled());
  });

  it("shows hosted connector setup actions", async () => {
    const user = userEvent.setup();
    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Connectors" }));
    await waitFor(() => expect(api.listMcpConnectorSettings).toHaveBeenCalled());
    expect(screen.getByText(/GitHub and Linear ship enabled by default/i)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Get token" })[0]).toHaveAttribute("href", "https://github.com/settings/tokens");
    expect(screen.getAllByRole("link", { name: "Guide" })[0]).toHaveAttribute(
      "href",
      "https://docs.github.com/en/copilot/how-tos/provide-context/use-mcp/set-up-the-github-mcp-server"
    );
    expect(screen.getByRole("link", { name: "Connect" })).toHaveAttribute("href", "https://supabase.com/dashboard/account/tokens");
    expect(screen.getByText("No custom MCP servers yet.")).toBeInTheDocument();
  });

  it("renders and manages custom MCP servers in settings", async () => {
    const user = userEvent.setup({ delay: null });
    localStorage.setItem("neutron-custom-mcp-servers", JSON.stringify([
      { id: "fs", name: "Filesystem", transport: "stdio", commandOrUrl: "npx filesystem", notes: "local", createdAt: "2026-01-01", updatedAt: "2026-01-01" },
    ]));
    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Connectors" }));
    expect(screen.getByText("Filesystem")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Add custom server/ }));
    await user.type(screen.getByLabelText("Name"), "Remote");
    await user.selectOptions(screen.getByLabelText("Transport"), "sse");
    await user.type(screen.getByLabelText("Command or URL"), "https://example.com/sse");
    await user.click(screen.getByRole("button", { name: "Save custom server" }));
    expect(await screen.findByText("Remote")).toBeInTheDocument();
    expect(localStorage.getItem("neutron-custom-mcp-servers")).toContain("https://example.com/sse");

    await user.click(screen.getAllByRole("button", { name: "Edit" })[1]);
    await user.clear(screen.getByLabelText("Name"));
    await user.type(screen.getByLabelText("Name"), "Remote SSE");
    await user.click(screen.getByRole("button", { name: "Update custom server" }));
    expect(await screen.findByText("Remote SSE")).toBeInTheDocument();

    await user.click(screen.getAllByRole("button", { name: /Delete/ })[1]);
    expect(screen.queryByText("Remote SSE")).not.toBeInTheDocument();
  }, 30_000);

  it("navigates to the account section", async () => {
    const user = userEvent.setup();
    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Account" }));
    expect(screen.getByRole("heading", { name: "Account" })).toBeInTheDocument();
    expect(screen.getByText("user@example.com")).toBeInTheDocument();
  });

  it("explains public-beta usage", async () => {
    const user = userEvent.setup();
    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Beta usage/ }));
    expect(screen.getByText(/Neutron does not sell credits during the public beta/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Cloud & AI/ }));
    expect(screen.getByRole("heading", { name: "Cloud & AI" })).toBeInTheDocument();
  });

  it("opens with initialSection", () => {
    render(<SettingsModal open onClose={vi.fn()} initialSection="account" />);
    expect(screen.getByRole("heading", { name: "Account" })).toBeInTheDocument();
  });

  it("opens the Help Center directly", () => {
    render(<SettingsModal open onClose={vi.fn()} initialSection="help" />);
    expect(screen.getByRole("heading", { name: "Help Center" })).toBeInTheDocument();
    expect(screen.getByText("Getting started")).toBeInTheDocument();
    expect(screen.getByText("Troubleshooting")).toBeInTheDocument();
    expect(screen.getByText("Use hosted GitHub, Linear, and Supabase MCP connections, or save custom MCP server configs locally for future builds.")).toBeInTheDocument();
    expect(screen.queryByText(/Neutron does not sell credits during the public beta/)).not.toBeInTheDocument();
  });

  it("shows Help Center content without a soon badge", async () => {
    const user = userEvent.setup();
    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Help Center" }));
    expect(screen.getByRole("heading", { name: "Cloud & AI" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "A note for beta testing" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Help Center" })).not.toHaveTextContent("Soon");
  });

  it("calls onClose when close button is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<SettingsModal open onClose={onClose} />);
    await user.click(screen.getByRole("button", { name: "Close settings" }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("initializes theme from light document class", () => {
    document.documentElement.classList.add("light");
    render(<SettingsModal open onClose={vi.fn()} />);
    expect(screen.getByRole("button", { name: /Light/ })).toHaveClass("border-accent");
  });

  it("saves and resets browser-local general settings", async () => {
    const user = userEvent.setup();
    render(<SettingsModal open onClose={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: /Light/ }));
    await user.click(screen.getByRole("button", { name: "Save Settings" }));

    expect(screen.getByText("Settings saved locally in this browser.")).toBeInTheDocument();
    expect(localStorage.getItem("neutron-local-settings")).toContain('"theme":"light"');

    await user.click(screen.getByRole("button", { name: "Reset" }));
    expect(screen.getByText("Settings reset to defaults.")).toBeInTheDocument();
  });

  it("opens Cloud & AI from the general API key shortcut", async () => {
    const user = userEvent.setup();
    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Configure AI model" }));
    expect(await screen.findByRole("heading", { name: "Cloud & AI" })).toBeInTheDocument();
  });

  it("loads and saves backend provider settings", async () => {
    const user = userEvent.setup();
    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Cloud & AI/ }));
    expect(await screen.findByLabelText("Provider")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Provider"), "openai");
    await user.type(screen.getByLabelText("API key"), "sk-test");
    await user.click(screen.getByRole("button", { name: "Save and use model" }));
    expect(api.updateProviderSettings).toHaveBeenCalledWith({
      provider: "openai",
      model: "gpt-4o",
      base_url: null,
      api_key: "sk-test",
    });
    expect(await screen.findByText("AI provider and model saved and activated for future builds.")).toBeInTheDocument();
  });

  it("applies provider defaults when switching Cloud & AI providers", async () => {
    const user = userEvent.setup();
    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Cloud & AI/ }));
    await screen.findByLabelText("Provider");

    await user.selectOptions(screen.getByLabelText("Provider"), "openrouter");
    expect(screen.getByLabelText("Model")).toHaveValue("openai/gpt-4o-mini");
    expect(screen.getByLabelText("Base URL")).toHaveValue("https://openrouter.ai/api/v1");

    await user.selectOptions(screen.getByLabelText("Provider"), "kimi");
    expect(screen.getByLabelText("Model")).toHaveValue("kimi-for-coding");
    expect(screen.getByLabelText("Base URL")).toHaveValue("https://api.kimi.com/coding/v1");

    await user.selectOptions(screen.getByLabelText("Provider"), "openai-compatible");
    expect(screen.getByLabelText("Model")).toHaveValue("");
    expect(screen.getByLabelText("Base URL")).toHaveValue("");

    await user.selectOptions(screen.getByLabelText("Provider"), "openai");
    expect(screen.getByLabelText("Model")).toHaveValue("gpt-4o");
    expect(screen.getByLabelText("Base URL")).toHaveValue("");
  });

  it("saves provider switch defaults instead of stale base URLs", async () => {
    const user = userEvent.setup();
    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Cloud & AI/ }));
    await screen.findByLabelText("Provider");
    await user.selectOptions(screen.getByLabelText("Provider"), "openrouter");
    await user.click(screen.getByRole("button", { name: "Save and use model" }));
    expect(api.updateProviderSettings).toHaveBeenCalledWith({
      provider: "openrouter",
      model: "openai/gpt-4o-mini",
      base_url: "https://openrouter.ai/api/v1",
      api_key: undefined,
    });
  });

  it("edits custom provider model and base URL", async () => {
    const user = userEvent.setup();
    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Cloud & AI/ }));
    await screen.findByLabelText("Provider");

    await user.selectOptions(screen.getByLabelText("Provider"), "custom");
    expect(screen.getByLabelText("Model")).toHaveAttribute("placeholder", "provider/model");
    expect(screen.getByLabelText("Base URL")).toHaveAttribute("placeholder", "https://api.example.com/v1");

    await user.clear(screen.getByLabelText("Model"));
    await user.type(screen.getByLabelText("Model"), "vendor/model");
    await user.type(screen.getByLabelText("Base URL"), "https://api.example.com/v1");
    await user.clear(screen.getByLabelText("Base URL"));
    await user.click(screen.getByRole("button", { name: "Save and use model" }));

    expect(api.updateProviderSettings).toHaveBeenCalledWith({
      provider: "custom",
      model: "vendor/model",
      base_url: null,
      api_key: undefined,
    });
  });

  it("shows provider load and save errors", async () => {
    const user = userEvent.setup();
    vi.mocked(api.getProviderSettings).mockRejectedValueOnce(new Error("load"));
    vi.mocked(api.updateProviderSettings).mockRejectedValueOnce(new Error("save"));
    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Cloud & AI/ }));
    expect(await screen.findByText("Unable to load provider settings. Please try again later.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save and use model" }));
    expect(await screen.findByText("Could not save provider settings. Check the provider, model, and base URL.")).toBeInTheDocument();
  });

  it("clears configured backend provider API key", async () => {
    const user = userEvent.setup();
    vi.mocked(api.getProviderSettings).mockResolvedValueOnce({
      provider: "openai-compatible",
      model: "kimchi/kimi-k2.7",
      base_url: "http://localhost:20128/v1",
      has_api_key: true,
      effective_model: "openai/kimchi/kimi-k2.7",
    });
    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Cloud & AI/ }));
    await screen.findByText(/Key status: configured/);
    await user.click(screen.getByRole("button", { name: "Clear Key" }));
    expect(api.clearProviderKey).toHaveBeenCalledWith("openai-compatible");
    expect(await screen.findByText("Provider API key cleared for your account.")).toBeInTheDocument();
  });

  it("shows provider key clear errors", async () => {
    const user = userEvent.setup();
    vi.mocked(api.getProviderSettings).mockResolvedValueOnce({
      provider: "openai-compatible",
      model: "kimchi/kimi-k2.7",
      base_url: "http://localhost:20128/v1",
      has_api_key: true,
      effective_model: "openai/kimchi/kimi-k2.7",
    });
    vi.mocked(api.clearProviderKey).mockRejectedValueOnce(new Error("clear"));
    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Cloud & AI/ }));
    await screen.findByText(/Key status: configured/);
    await user.click(screen.getByRole("button", { name: "Clear Key" }));
    expect(await screen.findByText("Could not clear provider API key.")).toBeInTheDocument();
  });

  it("shows Grok OAuth connect UI and starts login", async () => {
    const user = userEvent.setup();
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Cloud & AI/ }));
    await screen.findByLabelText("Provider");

    await user.selectOptions(screen.getByLabelText("Provider"), "xai-oauth");
    expect(screen.getByText("Sign in with your SuperGrok or X Premium+ account. No API key required.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Connect with Grok" }));

    expect(api.startXaiOAuth).toHaveBeenCalled();
    expect(openSpy).toHaveBeenCalledWith("https://auth.x.ai/device", "_blank", "noopener,noreferrer");
    expect(await screen.findByText("ABCD-1234")).toBeInTheDocument();
    openSpy.mockRestore();
  });

  it("shows Grok OAuth errors and disconnect flow", async () => {
    const user = userEvent.setup();
    vi.mocked(api.startXaiOAuth).mockRejectedValueOnce(new Error("start failed"));
    vi.mocked(api.listProviderSettings).mockResolvedValueOnce({
      active_provider: "xai-oauth",
      providers: [
        {
          provider: "xai-oauth",
          label: "Grok OAuth (SuperGrok)",
          model: "grok-4.5",
          base_url: "https://api.x.ai/v1",
          has_api_key: true,
          effective_model: "xai/grok-4.5",
          is_active: true,
          requires_base_url: false,
          requires_api_key: false,
          auth_method: "oauth",
          is_connected: true,
        },
      ],
    });
    vi.mocked(api.getProviderSettings).mockResolvedValueOnce({
      provider: "xai-oauth",
      model: "grok-4.5",
      base_url: "https://api.x.ai/v1",
      has_api_key: true,
      effective_model: "xai/grok-4.5",
    });
    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Cloud & AI/ }));
    await screen.findByLabelText("Provider");
    await user.selectOptions(screen.getByLabelText("Provider"), "xai-oauth");
    await user.click(screen.getByRole("button", { name: "Reconnect Grok" }));
    expect(await screen.findByText("Could not start Grok OAuth. Log in and try again.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Disconnect" }));
    expect(api.disconnectXaiOAuth).toHaveBeenCalled();
    expect(await screen.findByText("Grok OAuth disconnected.")).toBeInTheDocument();
  });

  it("shows provider activation errors", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listProviderSettings).mockResolvedValueOnce({
      active_provider: "openai-compatible",
      providers: [
        {
          provider: "openai-compatible",
          label: "OpenAI-compatible",
          model: "kimchi/kimi-k2.7",
          base_url: "http://localhost:20128/v1",
          has_api_key: false,
          effective_model: "openai/kimchi/kimi-k2.7",
          is_active: true,
          requires_base_url: true,
          requires_api_key: false,
          auth_method: "api_key",
          is_connected: false,
        },
        {
          provider: "openai",
          label: "OpenAI",
          model: "gpt-4o",
          base_url: null,
          has_api_key: true,
          effective_model: "openai/gpt-4o",
          is_active: false,
          requires_base_url: false,
          requires_api_key: true,
          auth_method: "api_key",
          is_connected: true,
        },
      ],
    });
    vi.mocked(api.activateProvider).mockRejectedValueOnce(new Error("activate failed"));
    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Cloud & AI/ }));
    await screen.findByRole("button", { name: /OpenAI.*openai\/gpt-4o/i });
    await user.click(screen.getByText("Activate"));
    expect(await screen.findByText("Could not activate provider. Log in and try again.")).toBeInTheDocument();
  });

  it("shows Grok OAuth disconnect errors", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listProviderSettings).mockResolvedValueOnce({
      active_provider: "xai-oauth",
      providers: [
        {
          provider: "xai-oauth",
          label: "Grok OAuth (SuperGrok)",
          model: "grok-4.5",
          base_url: "https://api.x.ai/v1",
          has_api_key: true,
          effective_model: "xai/grok-4.5",
          is_active: true,
          requires_base_url: false,
          requires_api_key: false,
          auth_method: "oauth",
          is_connected: true,
        },
      ],
    });
    vi.mocked(api.getProviderSettings).mockResolvedValueOnce({
      provider: "xai-oauth",
      model: "grok-4.5",
      base_url: "https://api.x.ai/v1",
      has_api_key: true,
      effective_model: "xai/grok-4.5",
    });
    vi.mocked(api.disconnectXaiOAuth).mockRejectedValueOnce(new Error("disconnect failed"));
    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Cloud & AI/ }));
    await screen.findByLabelText("Provider");
    await user.selectOptions(screen.getByLabelText("Provider"), "xai-oauth");
    await user.click(screen.getByRole("button", { name: "Disconnect" }));
    expect(await screen.findByText("Could not disconnect Grok OAuth.")).toBeInTheDocument();
  });

  it("activates an inactive provider from the provider cards", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listProviderSettings).mockResolvedValueOnce({
      active_provider: "openai-compatible",
      providers: [
        {
          provider: "openai-compatible",
          label: "OpenAI-compatible",
          model: "kimchi/kimi-k2.7",
          base_url: "http://localhost:20128/v1",
          has_api_key: false,
          effective_model: "openai/kimchi/kimi-k2.7",
          is_active: true,
          requires_base_url: true,
          requires_api_key: false,
          auth_method: "api_key",
          is_connected: false,
        },
        {
          provider: "openai",
          label: "OpenAI",
          model: "gpt-4o",
          base_url: null,
          has_api_key: true,
          effective_model: "openai/gpt-4o",
          is_active: false,
          requires_base_url: false,
          requires_api_key: true,
          auth_method: "api_key",
          is_connected: true,
        },
      ],
    });
    vi.mocked(api.activateProvider).mockResolvedValueOnce({
      provider: "openai",
      model: "gpt-4o",
      base_url: null,
      has_api_key: true,
      effective_model: "openai/gpt-4o",
    });
    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Cloud & AI/ }));
    await screen.findByRole("button", { name: /OpenAI.*openai\/gpt-4o/i });

    await user.click(screen.getByText("Activate"));
    expect(api.activateProvider).toHaveBeenCalledWith("openai");
    expect(await screen.findByText("OpenAI activated for builds.")).toBeInTheDocument();
  });

  it("switches provider settings when a provider card is clicked", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listProviderSettings).mockResolvedValueOnce({
      active_provider: "openai-compatible",
      providers: [
        {
          provider: "openai-compatible",
          label: "OpenAI-compatible",
          model: "kimchi/kimi-k2.7",
          base_url: "http://localhost:20128/v1",
          has_api_key: false,
          effective_model: "openai/kimchi/kimi-k2.7",
          is_active: true,
          requires_base_url: true,
          requires_api_key: false,
          auth_method: "api_key",
          is_connected: false,
        },
        {
          provider: "openai",
          label: "OpenAI",
          model: "gpt-4o",
          base_url: null,
          has_api_key: true,
          effective_model: "openai/gpt-4o",
          is_active: false,
          requires_base_url: false,
          requires_api_key: true,
          auth_method: "api_key",
          is_connected: true,
        },
      ],
    });
    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Cloud & AI/ }));
    const openAiCard = await screen.findByRole("button", { name: /OpenAI.*openai\/gpt-4o/i });

    await user.click(openAiCard);
    expect(screen.getByLabelText("Provider")).toHaveValue("openai");
    expect(screen.getByLabelText("Model")).toHaveValue("gpt-4o");
  });

  it("retries Grok OAuth polling while authorization is pending", async () => {
    const user = userEvent.setup();
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    vi.mocked(api.pollXaiOAuth)
      .mockResolvedValueOnce({ status: "pending", interval: 0.01 })
      .mockResolvedValueOnce({ status: "complete", connected: true });

    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Cloud & AI/ }));
    await screen.findByLabelText("Provider");
    await user.selectOptions(screen.getByLabelText("Provider"), "xai-oauth");
    await user.click(screen.getByRole("button", { name: "Connect with Grok" }));

    await waitFor(() => {
      expect(screen.getByText(oauthConnectedMessage)).toBeInTheDocument();
    });
    expect(api.pollXaiOAuth).toHaveBeenCalledTimes(2);
    openSpy.mockRestore();
  });

  it("completes Grok OAuth polling when authorization succeeds", async () => {
    const user = userEvent.setup();
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    vi.mocked(api.pollXaiOAuth).mockResolvedValueOnce({ status: "complete", connected: true });

    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Cloud & AI/ }));
    await screen.findByLabelText("Provider");
    await user.selectOptions(screen.getByLabelText("Provider"), "xai-oauth");
    await user.click(screen.getByRole("button", { name: "Connect with Grok" }));

    expect(await screen.findByText(oauthConnectedMessage)).toBeInTheDocument();
    openSpy.mockRestore();
  });

  it("falls back when OAuth completes but provider activation fails", async () => {
    const user = userEvent.setup();
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    vi.mocked(api.pollXaiOAuth).mockResolvedValueOnce({ status: "complete", connected: true });
    vi.mocked(api.activateProvider).mockRejectedValueOnce(new Error("activate failed"));

    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Cloud & AI/ }));
    await screen.findByLabelText("Provider");
    await user.selectOptions(screen.getByLabelText("Provider"), "xai-oauth");
    await user.click(screen.getByRole("button", { name: "Connect with Grok" }));

    expect(
      await screen.findByText("Grok OAuth connected. SuperGrok or X Premium+ subscription required."),
    ).toBeInTheDocument();
    openSpy.mockRestore();
  });

  it("shows Grok OAuth polling errors for denied, expired, and failed sessions", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "open").mockImplementation(() => null);
    vi.mocked(api.pollXaiOAuth)
      .mockResolvedValueOnce({ status: "denied" })
      .mockResolvedValueOnce({ status: "expired" })
      .mockRejectedValueOnce(new Error("poll failed"));

    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Cloud & AI/ }));
    await screen.findByLabelText("Provider");
    await user.selectOptions(screen.getByLabelText("Provider"), "xai-oauth");
    await user.click(screen.getByRole("button", { name: "Connect with Grok" }));
    expect(await screen.findByText("Grok OAuth authorization was denied.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Connect with Grok" }));
    expect(await screen.findByText("Grok OAuth session expired. Try again.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Connect with Grok" }));
    expect(await screen.findByText("Could not complete Grok OAuth login. Try again.")).toBeInTheDocument();
  });

  it("syncs provider models into a quick-pick list while keeping manual entry", async () => {
    const user = userEvent.setup();
    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Cloud & AI/ }));
    await screen.findByLabelText("Provider");
    await user.selectOptions(screen.getByLabelText("Provider"), "openai");
    expect(api.getProviderModels).toHaveBeenCalledWith("openai");
    expect(await screen.findByLabelText("Choose a synced model")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "gpt 4o" })).toBeInTheDocument();
    expect(screen.getByLabelText("Model")).toHaveAttribute("placeholder", "gpt-4o");
    expect(screen.getByText("Pick a synced model above or enter any model ID manually.")).toBeInTheDocument();
    const picker = screen.getByLabelText("Choose a synced model");
    const modelInput = screen.getByLabelText("Model");
    await user.selectOptions(picker, "gpt-4o");
    expect(modelInput).toHaveValue("gpt-4o");
    await user.selectOptions(picker, "");
    expect(modelInput).toHaveValue("gpt-4o");
  });

  it("falls back to manual model entry when sync fails", async () => {
    const user = userEvent.setup();
    vi.mocked(api.getProviderModels).mockImplementation((provider: LlmProvider) => {
      if (provider === "openai") return Promise.reject(new Error("sync failed"));
      const catalogs: Partial<Record<LlmProvider, Array<{ value: string; label: string }>>> = {
        "openai-compatible": [{ value: "kimchi/kimi-k2.7", label: "kimchi / kimi k2.7" }],
      };
      const models = catalogs[provider] ?? [];
      return Promise.resolve({
        provider,
        models,
        current: models[0]?.value ?? "",
        source: "catalog" as const,
      });
    });
    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Cloud & AI/ }));
    await screen.findByLabelText("Provider");
    await user.selectOptions(screen.getByLabelText("Provider"), "openai");
    expect(await screen.findByText("Could not sync models. Enter a model ID manually.")).toBeInTheDocument();
    expect(screen.getByLabelText("Model")).toHaveAttribute("placeholder", "gpt-4o");
  });

  it("prompts for a base URL before syncing openai-compatible models", async () => {
    const user = userEvent.setup();
    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Cloud & AI/ }));
    await screen.findByLabelText("Provider");
    await user.selectOptions(screen.getByLabelText("Provider"), "openai-compatible");
    expect(await screen.findByText("Add a base URL to sync models from your local endpoint.")).toBeInTheDocument();
  });

  it("saves the exact synced model selected for future builds", async () => {
    const user = userEvent.setup();
    vi.mocked(api.getProviderModels).mockImplementation((provider: LlmProvider) => Promise.resolve({
      provider,
      models: provider === "openai" ? [{ value: "gpt-4.1", label: "gpt 4.1" }] : [],
      current: provider === "openai" ? "gpt-4.1" : "",
      source: "catalog" as const,
    }));
    vi.mocked(api.updateProviderSettings).mockResolvedValueOnce({
      provider: "openai",
      model: "gpt-4.1",
      base_url: null,
      has_api_key: true,
      effective_model: "openai/gpt-4.1",
    });

    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Cloud & AI/ }));
    await screen.findByLabelText("Provider");
    await user.selectOptions(screen.getByLabelText("Provider"), "openai");
    await user.selectOptions(await screen.findByLabelText("Choose a synced model"), "gpt-4.1");
    await user.type(screen.getByLabelText("API key"), "sk-test");
    await user.click(screen.getByRole("button", { name: "Save and use model" }));

    expect(api.updateProviderSettings).toHaveBeenCalledWith({
      provider: "openai",
      model: "gpt-4.1",
      base_url: null,
      api_key: "sk-test",
    });
    expect(await screen.findByText(/Effective model:/)).toHaveTextContent("openai/gpt-4.1");
  });

  it("shows OAuth provider cards with disconnected status", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listProviderSettings).mockResolvedValueOnce({
      active_provider: "xai-oauth",
      providers: [
        {
          provider: "xai-oauth",
          label: "Grok OAuth (SuperGrok)",
          model: "grok-4.5",
          base_url: "https://api.x.ai/v1",
          has_api_key: false,
          effective_model: "xai/grok-4.5",
          is_active: true,
          requires_base_url: false,
          requires_api_key: false,
          auth_method: "oauth",
          is_connected: false,
        },
      ],
    });
    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Cloud & AI/ }));
    expect(await screen.findByText("OAuth: not connected")).toBeInTheDocument();
  });

  it("uses the default OAuth poll interval when none is returned", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "open").mockImplementation(() => null);
    vi.mocked(api.pollXaiOAuth)
      .mockResolvedValueOnce({ status: "pending" })
      .mockResolvedValueOnce({ status: "complete", connected: true });

    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Cloud & AI/ }));
    await screen.findByLabelText("Provider");
    await user.selectOptions(screen.getByLabelText("Provider"), "xai-oauth");
    await user.click(screen.getByRole("button", { name: "Connect with Grok" }));

    await waitFor(
      () => expect(screen.getByText(oauthConnectedMessage)).toBeInTheDocument(),
      { timeout: 7000 },
    );
    expect(api.pollXaiOAuth).toHaveBeenCalledTimes(2);
  }, 10000);

  it("shows account login prompt when signed out", async () => {
    const user = userEvent.setup();
    const locationSpy = vi.spyOn(window, "location", "get").mockReturnValue({ href: "" } as Location);
    useAuthStore.setState({ user: null, loading: false, error: null });

    render(<SettingsModal open onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Account" }));

    expect(screen.getByText("Not logged in")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Log in" }));
    expect(window.location.href).toBe("/login");
    locationSpy.mockRestore();
  });

  it("toggles theme between dark and light", async () => {
    const user = userEvent.setup();
    render(<SettingsModal open onClose={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: /Light/ }));
    expect(document.documentElement.classList.contains("light")).toBe(true);
    expect(localStorage.getItem("neutron-theme")).toBe("light");

    await user.click(screen.getByRole("button", { name: /Dark/ }));
    expect(document.documentElement.classList.contains("light")).toBe(false);
    expect(localStorage.getItem("neutron-theme")).toBe("dark");
  });
});
