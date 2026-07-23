import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SearchProviderSettingsPanel } from "@/components/settings/search-provider-settings-panel";
import { api, type SearchProviderSummary } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: {
    listSearchProviderSettings: vi.fn(),
    updateSearchProviderSettings: vi.fn(),
    clearSearchProviderKey: vi.fn(),
  },
}));

const brave: SearchProviderSummary = {
  provider: "brave",
  label: "Brave Search",
  description: "Independent web search.",
  docs_url: "https://example.com/brave",
  has_api_key: false,
  has_user_api_key: false,
};

const serper: SearchProviderSummary = {
  provider: "serper",
  label: "Serper",
  description: "Google search results.",
  docs_url: "https://example.com/serper",
  has_api_key: true,
  has_user_api_key: true,
};

describe("SearchProviderSettingsPanel", () => {
  beforeEach(() => {
    vi.mocked(api.listSearchProviderSettings).mockResolvedValue({ providers: [brave, serper] });
    vi.mocked(api.updateSearchProviderSettings).mockResolvedValue({ ...brave, has_api_key: true, has_user_api_key: true });
    vi.mocked(api.clearSearchProviderKey).mockResolvedValue({ ...serper, has_api_key: false, has_user_api_key: false });
  });

  it("loads providers and shows secure write-only status", async () => {
    render(<SearchProviderSettingsPanel />);

    expect(screen.getByText("Loading search providers...")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Brave Search" })).toBeInTheDocument();
    expect(screen.getByText("Write-only credentials")).toBeInTheDocument();
    const braveSection = screen.getByRole("heading", { name: "Brave Search" }).closest("section")!;
    expect(within(braveSection).getByRole("link", { name: "Get an API key" })).toHaveAttribute("href", "https://example.com/brave");
    expect(screen.getAllByText("Configured")).toHaveLength(1);
    expect(screen.getAllByText("Not configured")).toHaveLength(1);
    expect(screen.getByText("Your key")).toBeInTheDocument();
  });

  it("shows provider load failures", async () => {
    vi.mocked(api.listSearchProviderSettings).mockRejectedValueOnce(new Error("offline"));

    render(<SearchProviderSettingsPanel />);

    expect(await screen.findByText("Could not load search API settings. Log in and try again.")).toBeInTheDocument();
  });

  it("requires a key and saves a provider", async () => {
    const user = userEvent.setup();
    render(<SearchProviderSettingsPanel />);
    await screen.findByRole("heading", { name: "Brave Search" });

    await user.click(screen.getByRole("button", { name: "Save key" }));
    expect(screen.getByText("Paste a Brave Search API key before saving.")).toBeInTheDocument();

    const input = screen.getByLabelText("Brave Search API key");
    await user.type(input, " brave-secret ");
    await user.click(screen.getByRole("button", { name: "Save key" }));

    await waitFor(() => expect(api.updateSearchProviderSettings).toHaveBeenCalledWith({
      provider: "brave",
      api_key: "brave-secret",
    }));
    expect(await screen.findByText("Brave Search API key saved securely.")).toBeInTheDocument();
    expect(input).toHaveValue("");
    const braveSection = screen.getByRole("heading", { name: "Brave Search" }).closest("section")!;
    expect(within(braveSection).getByRole("button", { name: "Replace key" })).toBeInTheDocument();
  });

  it("shows save failures", async () => {
    vi.mocked(api.updateSearchProviderSettings).mockRejectedValueOnce(new Error("failed"));
    const user = userEvent.setup();
    render(<SearchProviderSettingsPanel />);
    const input = await screen.findByLabelText("Brave Search API key");

    await user.type(input, "secret");
    await user.click(screen.getByRole("button", { name: "Save key" }));

    expect(await screen.findByText("Could not save the Brave Search API key.")).toBeInTheDocument();
  });

  it("removes account keys and reports server fallback", async () => {
    vi.mocked(api.clearSearchProviderKey).mockResolvedValueOnce({ ...serper, has_user_api_key: false });
    const user = userEvent.setup();
    render(<SearchProviderSettingsPanel />);
    await screen.findByRole("heading", { name: "Serper" });

    await user.click(screen.getByRole("button", { name: "Remove" }));

    expect(await screen.findByText("Serper key removed. The server default is now in use.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remove" })).not.toBeInTheDocument();
  });

  it("labels server defaults without offering a remove action", async () => {
    vi.mocked(api.listSearchProviderSettings).mockResolvedValueOnce({
      providers: [{ ...serper, has_user_api_key: false }],
    });

    render(<SearchProviderSettingsPanel />);

    expect(await screen.findByText("Server default")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remove" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Replace key" })).toBeInTheDocument();
  });

  it("removes keys completely and handles clear failures", async () => {
    const user = userEvent.setup();
    render(<SearchProviderSettingsPanel />);
    await screen.findByRole("heading", { name: "Serper" });

    await user.click(screen.getByRole("button", { name: "Remove" }));
    expect(await screen.findByText("Serper API key removed.")).toBeInTheDocument();

    vi.mocked(api.listSearchProviderSettings).mockResolvedValueOnce({ providers: [serper] });
    vi.mocked(api.clearSearchProviderKey).mockRejectedValueOnce(new Error("failed"));
    render(<SearchProviderSettingsPanel />);
    const removeButtons = await screen.findAllByRole("button", { name: "Remove" });
    await user.click(removeButtons.at(-1)!);
    expect(await screen.findByText("Could not remove the Serper API key.")).toBeInTheDocument();
  });
});
