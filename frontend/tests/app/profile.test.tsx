import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import ProfilePage from "@/app/profile/page";

vi.mock("@/lib/api", () => ({
  api: {
    getAvailableModels: vi.fn().mockResolvedValue({
      models: [
        { value: "openai/gpt-4o", label: "OpenAI GPT-4o" },
      ],
      current: "openai/gpt-4o",
    }),
    getAgentModels: vi.fn().mockResolvedValue({
      provider: "openai-compatible",
      default_model: "kimchi/kimi-k2.7",
      agents: [],
    }),
    updateAgentModels: vi.fn(),
    getProviderSettings: vi.fn().mockResolvedValue({
      provider: "openai-compatible",
      model: "kimchi/kimi-k2.7",
      base_url: "http://localhost:20128/v1",
      has_api_key: false,
      effective_model: "openai/kimchi/kimi-k2.7",
    }),
    updateProviderSettings: vi.fn(),
    listProviderSettings: vi.fn().mockResolvedValue({
      active_provider: "openai-compatible",
      providers: [],
    }),
    activateProvider: vi.fn(),
    clearProviderKey: vi.fn(),
    startXaiOAuth: vi.fn(),
    pollXaiOAuth: vi.fn(),
    disconnectXaiOAuth: vi.fn(),
    listSearchProviderSettings: vi.fn().mockResolvedValue({ providers: [] }),
    updateSearchProviderSettings: vi.fn(),
    clearSearchProviderKey: vi.fn(),
  },
}));

describe("ProfilePage", () => {
  it("renders the profile heading and cards", () => {
    render(<ProfilePage />);
    expect(screen.getByRole("heading", { name: "Profile" })).toBeInTheDocument();
    expect(screen.getByText("Manage your local Neutron workspace.")).toBeInTheDocument();
    expect(screen.getByText("Global Control")).toBeInTheDocument();
    expect(screen.getByText("Credentials")).toBeInTheDocument();
    expect(screen.getByText("Search APIs")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open Settings" })).toBeInTheDocument();
  });

  it("opens the settings modal when Global Control is clicked", async () => {
    const user = userEvent.setup();
    render(<ProfilePage />);
    await user.click(screen.getByText("Global Control"));
    expect(screen.getByRole("button", { name: "Close settings" })).toBeInTheDocument();
    expect(screen.getByText("AI provider and model")).toBeInTheDocument();
  });

  it("opens the AI provider settings when Credentials is clicked", async () => {
    const user = userEvent.setup();
    render(<ProfilePage />);
    await user.click(screen.getByText("Credentials"));
    expect(screen.getByRole("button", { name: "Close settings" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Cloud & AI" })).toBeInTheDocument();
    expect(screen.getByLabelText("Provider")).toBeInTheDocument();
  });

  it("opens the settings modal when Open Settings button is clicked", async () => {
    const user = userEvent.setup();
    render(<ProfilePage />);
    await user.click(screen.getByRole("button", { name: "Open Settings" }));
    expect(screen.getByRole("button", { name: "Close settings" })).toBeInTheDocument();
  });

  it("opens search API settings from the profile card", async () => {
    const user = userEvent.setup();
    render(<ProfilePage />);

    await user.click(screen.getByRole("heading", { name: "Search APIs" }));

    expect(await screen.findByText("Write-only credentials")).toBeInTheDocument();
  });

  it("closes the settings modal", async () => {
    const user = userEvent.setup();
    render(<ProfilePage />);
    await user.click(screen.getByRole("button", { name: "Open Settings" }));
    expect(screen.getByRole("button", { name: "Close settings" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Close settings" }));
    expect(screen.queryByRole("button", { name: "Close settings" })).not.toBeInTheDocument();
  });

  it("opens settings from query param", () => {
    window.history.pushState({}, "", "/profile?settings=globalControl");
    render(<ProfilePage />);
    expect(screen.getByRole("button", { name: "Close settings" })).toBeInTheDocument();
  });
});
