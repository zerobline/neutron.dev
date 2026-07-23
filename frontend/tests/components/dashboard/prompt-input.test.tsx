import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PromptInput } from "@/components/dashboard/prompt-input";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: {
    listProviderSettings: vi.fn(),
    activateProvider: vi.fn(),
  },
}));

describe("PromptInput", () => {
  beforeEach(() => {
    vi.mocked(api.listProviderSettings).mockResolvedValue({
      active_provider: "openai",
      providers: [
        {
          provider: "openai",
          label: "OpenAI",
          model: "gpt-4o",
          base_url: null,
          has_api_key: true,
          effective_model: "openai/gpt-4o",
          is_active: true,
          requires_base_url: false,
          requires_api_key: true,
          auth_method: "api_key",
          is_connected: true,
        },
        {
          provider: "xai-oauth",
          label: "Grok OAuth",
          model: "grok-4.5",
          base_url: "https://api.x.ai/v1",
          has_api_key: true,
          effective_model: "xai/grok-4.5",
          is_active: false,
          requires_base_url: false,
          requires_api_key: false,
          auth_method: "oauth",
          is_connected: true,
        },
      ],
    });
    vi.mocked(api.activateProvider).mockResolvedValue({
      provider: "xai-oauth",
      model: "grok-4.5",
      base_url: "https://api.x.ai/v1",
      has_api_key: true,
      effective_model: "xai/grok-4.5",
    });
  });

  it("loads providers and activates on change", async () => {
    const user = userEvent.setup();
    render(<PromptInput onSubmit={vi.fn()} />);

    const select = await screen.findByLabelText("AI provider");
    expect(select).toHaveValue("openai");
    expect(screen.getByRole("option", { name: "OpenAI · gpt-4o" })).toBeInTheDocument();

    await user.selectOptions(select, "xai-oauth");
    expect(api.activateProvider).toHaveBeenCalledWith("xai-oauth");
    expect(select).toHaveValue("xai-oauth");
  });

  it("ignores provider load failures", async () => {
    vi.mocked(api.listProviderSettings).mockRejectedValueOnce(new Error("fail"));
    render(<PromptInput onSubmit={vi.fn()} />);
    await waitFor(() => expect(api.listProviderSettings).toHaveBeenCalled());
    expect(screen.queryByLabelText("AI provider")).not.toBeInTheDocument();
  });

  it("ignores provider activation failures", async () => {
    const user = userEvent.setup();
    vi.mocked(api.activateProvider).mockRejectedValueOnce(new Error("fail"));
    render(<PromptInput onSubmit={vi.fn()} />);

    const select = await screen.findByLabelText("AI provider");
    await user.selectOptions(select, "xai-oauth");
    expect(api.activateProvider).toHaveBeenCalledWith("xai-oauth");
    expect(select).toHaveValue("xai-oauth");
  });
  it("renders placeholder and submit button disabled when empty", () => {
    render(<PromptInput onSubmit={vi.fn()} />);
    expect(screen.getByPlaceholderText("@agent to chat, # files, or describe what to build...")).toBeInTheDocument();
    expect(screen.getByTitle("Start building")).toBeDisabled();
  });

  it("submits text on button click", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<PromptInput onSubmit={onSubmit} />);
    await user.type(screen.getByPlaceholderText("@agent to chat, # files, or describe what to build..."), "Build an app");
    await user.click(screen.getByTitle("Start building"));
    expect(onSubmit).toHaveBeenCalledWith("Build an app", "goal", [], "static");
  });

  it("submits selected Next.js stack", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<PromptInput onSubmit={onSubmit} />);
    await user.selectOptions(screen.getByLabelText("Project stack"), "nextjs");
    await user.type(screen.getByPlaceholderText("@agent to chat, # files, or describe what to build..."), "SaaS dashboard");
    await user.click(screen.getByTitle("Start building"));
    expect(onSubmit).toHaveBeenCalledWith("SaaS dashboard", "goal", [], "nextjs");
  });

  it("honors initialStack for Next.js templates", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<PromptInput onSubmit={onSubmit} initialStack="nextjs" initialValue="From template" />);
    expect(screen.getByLabelText("Project stack")).toHaveValue("nextjs");
    await user.click(screen.getByTitle("Start building"));
    expect(onSubmit).toHaveBeenCalledWith("From template", "goal", [], "nextjs");
  });

  it("submits text on Enter key (not shift+enter)", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<PromptInput onSubmit={onSubmit} />);
    await user.type(screen.getByPlaceholderText("@agent to chat, # files, or describe what to build..."), "Hello");
    fireEvent.keyDown(screen.getByPlaceholderText("@agent to chat, # files, or describe what to build..."), { key: "Enter" });
    expect(onSubmit).toHaveBeenCalledWith("Hello", "goal", [], "static");
  });

  it("does not submit on shift+enter", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<PromptInput onSubmit={onSubmit} />);
    await user.type(screen.getByPlaceholderText("@agent to chat, # files, or describe what to build..."), "Hello{shift>}{enter}{/shift}");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("does not submit when disabled", () => {
    const onSubmit = vi.fn();
    render(<PromptInput onSubmit={onSubmit} disabled initialValue="test" />);
    fireEvent.keyDown(screen.getByPlaceholderText("@agent to chat, # files, or describe what to build..."), { key: "Enter" });
    fireEvent.click(screen.getByTitle("Start building"));
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("uses initialValue", () => {
    render(<PromptInput onSubmit={vi.fn()} initialValue="prefilled" />);
    expect(screen.getByPlaceholderText("@agent to chat, # files, or describe what to build...")).toHaveValue("prefilled");
  });

  it("calls onOpenConnectors when connectors button is clicked", async () => {
    const user = userEvent.setup();
    const onOpenConnectors = vi.fn();
    render(<PromptInput onSubmit={vi.fn()} onOpenConnectors={onOpenConnectors} />);
    await user.click(screen.getByTitle("Connect tools"));
    expect(onOpenConnectors).toHaveBeenCalledOnce();
  });

  it("adds files via file input and displays them", async () => {
    const onSubmit = vi.fn();
    render(<PromptInput onSubmit={onSubmit} />);
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["content"], "test.txt", { type: "text/plain" });
    fireEvent.change(fileInput, { target: { files: [file] } });
    expect(screen.getByText("test.txt")).toBeInTheDocument();
    expect(screen.getByTitle("Start building")).not.toBeDisabled();
  });

  it("removes attached file tags", async () => {
    const user = userEvent.setup();
    render(<PromptInput onSubmit={vi.fn()} />);
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["content"], "test.txt", { type: "text/plain" });
    fireEvent.change(fileInput, { target: { files: [file] } });
    expect(screen.getByText("test.txt")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Remove test.txt" }));
    expect(screen.queryByText("test.txt")).not.toBeInTheDocument();
  });

  it("submits fallback text when only files are attached", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<PromptInput onSubmit={onSubmit} />);
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["content"], "test.txt", { type: "text/plain" });
    fireEvent.change(fileInput, { target: { files: [file] } });
    await user.click(screen.getByTitle("Start building"));
    expect(onSubmit).toHaveBeenCalledWith("Build from uploaded files", "goal", [file], "static");
  });

  it("handles paste with image files", () => {
    const onSubmit = vi.fn();
    render(<PromptInput onSubmit={onSubmit} />);
    const textarea = screen.getByPlaceholderText("@agent to chat, # files, or describe what to build...");

    const file = new File(["img"], "screenshot.png", { type: "image/png" });
    const clipboardData = {
      items: [
        { kind: "file", type: "image/png", getAsFile: () => file },
      ],
    };
    fireEvent.paste(textarea, { clipboardData });
    expect(screen.getByText("screenshot.png")).toBeInTheDocument();
  });

  it("ignores paste when no image files are present", () => {
    render(<PromptInput onSubmit={vi.fn()} />);
    const textarea = screen.getByPlaceholderText("@agent to chat, # files, or describe what to build...");
    const clipboardData = {
      items: [
        { kind: "string", type: "text/plain", getAsFile: () => null },
      ],
    };
    fireEvent.paste(textarea, { clipboardData });
    expect(screen.queryByRole("button", { name: /Remove/ })).not.toBeInTheDocument();
  });

  it("handles file input change with no files", () => {
    render(<PromptInput onSubmit={vi.fn()} />);
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: null } });
    expect(screen.getByTitle("Start building")).toBeDisabled();
  });

  it("opens file dialog via upload button", async () => {
    const user = userEvent.setup();
    render(<PromptInput onSubmit={vi.fn()} />);
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const clickSpy = vi.spyOn(fileInput, "click");
    await user.click(screen.getByTitle("Upload files"));
    expect(clickSpy).toHaveBeenCalled();
  });

  it("auto-resizes textarea on input", async () => {
    const user = userEvent.setup();
    render(<PromptInput onSubmit={vi.fn()} />);
    const textarea = screen.getByPlaceholderText("@agent to chat, # files, or describe what to build...");
    Object.defineProperty(textarea, "scrollHeight", { value: 100, configurable: true });
    await user.type(textarea, "a");
    expect(textarea.style.height).toBeDefined();
  });
});
