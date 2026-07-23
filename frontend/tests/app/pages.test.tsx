import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import HomePage from "@/app/page";
import RootLayout, { metadata } from "@/app/layout";
import DashboardPage from "@/app/dashboard/page";
import LoginPage from "@/app/login/page";
import TemplatesPage from "@/app/templates/page";
import ProjectWorkspace from "@/app/project/[id]/page";
import { api } from "@/lib/api";

import { useAuthStore } from "@/stores/auth-store";
import { useProjectStore } from "@/stores/project-store";
import { fileFixture, messageFixture, projectFixture, templateFixture } from "../utils/fixtures";
import { pushMock, setMockParams, setMockSearchParams } from "../mocks/next-navigation";

vi.mock("@vercel/analytics/next", () => ({
  Analytics: () => null,
}));

vi.mock("@/lib/api", () => ({
  api: {
    me: vi.fn(),
    createProject: vi.fn(),
    listProjects: vi.fn(),
    getProject: vi.fn(),
    deleteProject: vi.fn(),
    getProjectFiles: vi.fn(),
    getProjectMessages: vi.fn(),
    getProjectConnectors: vi.fn(),
    getProjectCheckpoints: vi.fn(),
    saveProjectConnectors: vi.fn(),
    listBuiltinSkills: vi.fn(),
    getProjectSkills: vi.fn(),
    saveProjectSkills: vi.fn(),
    createProjectSkill: vi.fn(),
    deleteProjectSkill: vi.fn(),
    listTemplates: vi.fn(),
    getTemplate: vi.fn(),
    uploadFile: vi.fn(),
    listProviderSettings: vi.fn(),
    getProviderSettings: vi.fn(),
    getAvailableModels: vi.fn(),
    listMcpConnectorSettings: vi.fn(),
    updateMcpConnectorSettings: vi.fn(),
    clearMcpConnectorKey: vi.fn(),
  },
  getProjectDownloadUrl: vi.fn((projectId: string) => `http://localhost:8000/api/projects/${projectId}/download`),
  getWsUrl: vi.fn((projectId: string) => `ws://test/ws/project/${projectId}`),
}));

const websocketMocks = vi.hoisted(() => ({
  send: vi.fn(),
  startBuild: vi.fn(),
  resumeBuild: vi.fn(),
  forkBuild: vi.fn(),
  sendFeedback: vi.fn(),
}));

vi.mock("@/hooks/use-websocket", () => ({
  useProjectWebSocket: vi.fn(() => ({
    send: websocketMocks.send,
    startBuild: websocketMocks.startBuild,
    resumeBuild: websocketMocks.resumeBuild,
    forkBuild: websocketMocks.forkBuild,
    sendFeedback: websocketMocks.sendFeedback,
    connected: true,
  })),
}));

const testUser = { id: "user-1", email: "user@example.com", display_name: null, created_at: "2026-01-01" };

function seedSignedInAuth() {
  useAuthStore.setState({
    user: testUser,
    loading: false,
    error: null,
    refreshMe: async () => {
      useAuthStore.setState({ user: testUser, loading: false, error: null });
    },
  });
}

function seedSignedOutAuth() {
  useAuthStore.setState({
    user: null,
    loading: false,
    error: null,
    refreshMe: async () => {
      useAuthStore.setState({ user: null, loading: false, error: null });
    },
  });
}

async function waitForSignedIn() {
  await waitFor(() => expect(useAuthStore.getState().user).not.toBeNull());
}

describe("app pages", () => {
  beforeEach(() => {
    window.history.pushState({}, "", "/");
    sessionStorage.clear();
    seedSignedInAuth();
    vi.mocked(api.me).mockResolvedValue(testUser);
    vi.mocked(api.listProjects).mockResolvedValue([]);
    vi.mocked(api.listProviderSettings).mockResolvedValue({ active_provider: "openai", providers: [] });
    vi.mocked(api.getProviderSettings).mockResolvedValue({
      provider: "openai-compatible",
      model: "kimchi/kimi-k2.7",
      base_url: "http://localhost:20128/v1",
      has_api_key: false,
      effective_model: "openai/kimchi/kimi-k2.7",
    });
    vi.mocked(api.getAvailableModels).mockResolvedValue({
      models: [{ value: "openai/gpt-4o", label: "OpenAI GPT-4o" }],
      current: "openai/gpt-4o",
    });
    vi.mocked(api.getTemplate).mockResolvedValue(templateFixture);
    vi.mocked(api.createProject).mockResolvedValue(projectFixture);
    vi.mocked(api.deleteProject).mockResolvedValue({ ok: true });
    vi.mocked(api.listTemplates).mockResolvedValue([templateFixture, { ...templateFixture, id: "custom", icon: "unknown", name: "Custom" }]);
    vi.mocked(api.getProject).mockResolvedValue(projectFixture);
    vi.mocked(api.getProjectMessages).mockResolvedValue([{ ...messageFixture, created_at: "2026-01-02T00:00:00.000Z" }]);
    vi.mocked(api.getProjectFiles).mockResolvedValue([fileFixture]);
    vi.mocked(api.getProjectConnectors).mockResolvedValue({ custom_mcp_servers: [] });
    vi.mocked(api.getProjectCheckpoints).mockResolvedValue({ checkpoints: [], latest: null });
    vi.mocked(api.saveProjectConnectors).mockResolvedValue({ custom_mcp_servers: [] });
    vi.mocked(api.listBuiltinSkills).mockResolvedValue([]);
    vi.mocked(api.getProjectSkills).mockResolvedValue({ skills: [] });
    vi.mocked(api.saveProjectSkills).mockResolvedValue({ skills: [] });
    vi.mocked(api.createProjectSkill).mockResolvedValue({ skills: [] });
    vi.mocked(api.deleteProjectSkill).mockResolvedValue({ skills: [] });
    vi.mocked(api.listMcpConnectorSettings).mockResolvedValue({
      connectors: [
        {
          key: "github",
          label: "GitHub",
          description: "GitHub MCP",
          docs_url: "https://docs.github.com",
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
  });

  it("renders the home page sections", () => {
    render(<HomePage />);
    expect(screen.getByRole("heading", { name: /Turn an idea into a working prototype/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /What Neutron helps with/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "How it works" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Start from a Template" })).toBeInTheDocument();
  });

  it("exports metadata and renders root layout", () => {
    const element = RootLayout({ children: <main key="child">Child</main> });
    expect(metadata).toMatchObject({ title: "Neutron | CrewAI project builder" });
    expect(element.type).toBe("html");
    expect(element.props.lang).toBe("en");
    expect(element.props.suppressHydrationWarning).toBe(true);
    const children = Array.isArray(element.props.children)
      ? element.props.children
      : [element.props.children];
    expect(children.map((child: { type: string }) => child.type)).toEqual(["head", "body"]);
    const body = children.find((child: { type: string }) => child.type === "body");
    expect(body?.props?.children).toEqual([<main key="child">Child</main>, null]);
  });

  it("renders analytics when vercel analytics is enabled", async () => {
    vi.stubEnv("NEXT_PUBLIC_VERCEL_ANALYTICS", "true");
    vi.resetModules();
    const { default: EnabledLayout } = await import("@/app/layout");
    const element = EnabledLayout({ children: <main>Child</main> });
    const children = Array.isArray(element.props.children)
      ? element.props.children
      : [element.props.children];
    const body = children.find((child: { type: string }) => child.type === "body");
    const bodyChildren = body?.props?.children;
    expect(Array.isArray(bodyChildren) ? bodyChildren.length : 1).toBe(2);
    expect(bodyChildren?.[1]).not.toBeNull();
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("renders dashboard loading, prefills template prompt, and creates a project", async () => {
    const user = userEvent.setup();
    window.history.pushState({}, "", "/dashboard?template=saas");
    setMockSearchParams({ template: "saas" });
    render(<DashboardPage />);
    expect(document.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);

    await waitForSignedIn();
    await waitFor(() => expect(api.listProjects).toHaveBeenCalled());
    expect(screen.getByRole("heading", { name: "Your next product starts here." })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByPlaceholderText("@agent to chat, # files, or describe what to build...")).toHaveValue(templateFixture.prompt));
    await user.click(screen.getByTitle("Start building"));

    await waitFor(() => expect(api.createProject).toHaveBeenCalledWith({
      name: templateFixture.prompt,
      description: templateFixture.prompt,
      template: templateFixture.id,
      stack: "static",
    }));
    expect(api.saveProjectConnectors).toHaveBeenCalledWith("project-1", {
      default_mcps: [
        { key: "github", enabled: true },
        { key: "linear", enabled: true },
      ],
      custom_mcp_servers: [],
    });
    expect(pushMock).toHaveBeenCalledWith("/project/project-1?autostart=true&mode=goal");
  });

  it("renders the login page", () => {
    render(<LoginPage />);
    expect(screen.getByRole("heading", { name: "Log in to Neutron" })).toBeInTheDocument();
  });

  it("waits for auth before loading dashboard projects", async () => {
    useAuthStore.setState({
      user: null,
      loading: true,
      error: null,
      refreshMe: async () => {},
    });
    render(<DashboardPage />);
    expect(api.listProjects).not.toHaveBeenCalled();

    useAuthStore.setState({ user: testUser, loading: false });
    await waitFor(() => expect(api.listProjects).toHaveBeenCalled());
  });

  it("redirects to login when submitting during auth loading without a user", async () => {
    const user = userEvent.setup();
    useAuthStore.setState({
      user: null,
      loading: true,
      error: null,
      refreshMe: async () => {},
    });
    render(<DashboardPage />);
    await user.type(screen.getByPlaceholderText("@agent to chat, # files, or describe what to build..."), "Build an app");
    await user.click(screen.getByTitle("Start building"));
    expect(pushMock).toHaveBeenCalledWith("/login");
    expect(api.createProject).not.toHaveBeenCalled();
  });

  it("shows a login prompt on dashboard when signed out", async () => {
    seedSignedOutAuth();
    render(<DashboardPage />);

    expect(await screen.findByRole("heading", { name: "Log in to start building." })).toBeInTheDocument();
    await waitFor(() => expect(useAuthStore.getState().user).toBeNull());
    expect(api.listProjects).not.toHaveBeenCalled();
    expect(screen.getByRole("link", { name: "Log in" })).toHaveAttribute("href", "/login");
  });

  it("renders dashboard projects, deletes with confirmation, and handles template/list errors", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listProjects).mockResolvedValueOnce([projectFixture]).mockRejectedValueOnce(new Error("fail"));
    vi.mocked(api.getTemplate).mockRejectedValueOnce(new Error("fail"));
    const { unmount } = render(<DashboardPage />);
    await waitForSignedIn();
    expect(await screen.findByText("Project One")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Delete Project One" }));
    expect(screen.getByRole("heading", { name: "Delete project?" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(api.deleteProject).not.toHaveBeenCalled();
    expect(screen.getByText("Project One")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Delete Project One" }));
    await user.click(screen.getByRole("button", { name: "Delete Project" }));
    await waitFor(() => expect(api.deleteProject).toHaveBeenCalledWith("project-1"));
    expect(screen.queryByText("Project One")).not.toBeInTheDocument();
    expect(screen.queryByText("Recent Projects")).not.toBeInTheDocument();

    unmount();
    render(<DashboardPage />);
    await waitFor(() => expect(api.listProjects).toHaveBeenCalledTimes(2));
  });

  it("keeps dashboard delete dialog open after a delete error", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listProjects).mockResolvedValueOnce([projectFixture]);
    vi.mocked(api.deleteProject).mockRejectedValueOnce(new Error("fail"));
    render(<DashboardPage />);
    await waitForSignedIn();
    expect(await screen.findByText("Project One")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Delete Project One" }));
    await user.click(screen.getByRole("button", { name: "Delete Project" }));

    expect(await screen.findByText("Could not delete project. Try again.")).toBeInTheDocument();
    expect(screen.getByText("Project One")).toBeInTheDocument();
  });

  it("leaves prompt empty when template has no prompt", async () => {
    window.history.pushState({}, "", "/dashboard?template=empty");
    vi.mocked(api.getTemplate).mockResolvedValueOnce({ ...templateFixture, prompt: "" });
    render(<DashboardPage />);
    await waitForSignedIn();
    await waitFor(() => expect(api.getTemplate).toHaveBeenCalledWith("empty"));
    expect(screen.getByPlaceholderText("@agent to chat, # files, or describe what to build...")).toHaveValue("");
  });

  it("leaves prompt empty when template prompt is missing", async () => {
    window.history.pushState({}, "", "/dashboard?template=missing");
    vi.mocked(api.getTemplate).mockResolvedValueOnce({ ...templateFixture, prompt: undefined as never });
    render(<DashboardPage />);
    await waitForSignedIn();
    await waitFor(() => expect(api.getTemplate).toHaveBeenCalledWith("missing"));
    expect(screen.getByPlaceholderText("@agent to chat, # files, or describe what to build...")).toHaveValue("");
  });

  it("shows error when template fetch fails", async () => {
    window.history.pushState({}, "", "/dashboard?template=bad");
    vi.mocked(api.getTemplate).mockReset().mockRejectedValueOnce(new Error("fail"));
    render(<DashboardPage />);
    await waitForSignedIn();
    expect(await screen.findByText("Could not load template.")).toBeInTheDocument();
  });

  it("shows create error when project creation fails", async () => {
    const user = userEvent.setup();
    vi.mocked(api.createProject).mockRejectedValueOnce(new Error("fail"));
    render(<DashboardPage />);
    await waitForSignedIn();
    await waitFor(() => expect(api.listProjects).toHaveBeenCalled());

    await user.type(screen.getByPlaceholderText("@agent to chat, # files, or describe what to build..."), "My app");
    await user.click(screen.getByTitle("Start building"));

    expect(await screen.findByText("Could not create the project. Please try again.")).toBeInTheDocument();
  });

  it("opens connectors modal from the dashboard connector bar", async () => {
    const user = userEvent.setup();
    render(<DashboardPage />);
    await waitForSignedIn();
    await waitFor(() => expect(api.listProjects).toHaveBeenCalled());
    await user.click(screen.getByRole("button", { name: /Connectors/i }));
    expect(screen.getByRole("heading", { name: "Connectors" })).toBeInTheDocument();
  });

  it("opens team skills panel from the dashboard before a build", async () => {
    const user = userEvent.setup();
    render(<DashboardPage />);
    await waitForSignedIn();
    await waitFor(() => expect(api.listProjects).toHaveBeenCalled());
    await user.click(screen.getByRole("button", { name: /Team Skills/i }));
    expect(screen.getByRole("heading", { name: "Team Skills" })).toBeInTheDocument();
    await waitFor(() => expect(api.listBuiltinSkills).toHaveBeenCalled());
  });

  it("opens connectors modal from PromptInput connector button", async () => {
    const user = userEvent.setup();
    render(<DashboardPage />);
    await waitForSignedIn();
    await waitFor(() => expect(api.listProjects).toHaveBeenCalled());
    await user.click(screen.getByTitle("Connect tools"));
    expect(screen.getByRole("heading", { name: "Connectors" })).toBeInTheDocument();
  });

  it("routes the default autonomous mode to goal build mode", async () => {
    const user = userEvent.setup();
    render(<DashboardPage />);
    await waitForSignedIn();
    await waitFor(() => expect(api.listProjects).toHaveBeenCalled());

    await user.type(screen.getByPlaceholderText("@agent to chat, # files, or describe what to build..."), "Goal app");
    await user.click(screen.getByTitle("Start building"));

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/project/project-1?autostart=true&mode=goal"));
  });

  it("uploads files during project creation", async () => {
    const user = userEvent.setup();
    vi.mocked(api.uploadFile).mockResolvedValue({ name: "img.png", size: 100, type: "image/png", path: "/uploads/img.png" });
    render(<DashboardPage />);
    await waitForSignedIn();
    await waitFor(() => expect(api.listProjects).toHaveBeenCalled());

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["img"], "img.png", { type: "image/png" });
    fireEvent.change(fileInput, { target: { files: [file] } });

    await user.type(screen.getByPlaceholderText("@agent to chat, # files, or describe what to build..."), "With file");
    await user.click(screen.getByTitle("Start building"));
    await waitFor(() => expect(api.uploadFile).toHaveBeenCalledWith("project-1", file));
    expect(pushMock).toHaveBeenCalledWith("/project/project-1?autostart=true&mode=goal");
  });

  it("closes connectors modal from the close button", async () => {
    const user = userEvent.setup();
    render(<DashboardPage />);
    await waitForSignedIn();
    await waitFor(() => expect(api.listProjects).toHaveBeenCalled());
    await user.click(screen.getByRole("button", { name: /Connectors/i }));
    expect(screen.getByRole("heading", { name: "Connectors" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Close connectors" }));
    expect(screen.queryByRole("heading", { name: "Connectors" })).not.toBeInTheDocument();
  });

  it("truncates long project names during creation", async () => {
    const user = userEvent.setup();
    const longPrompt = "a".repeat(60);
    render(<DashboardPage />);
    await waitForSignedIn();
    await waitFor(() => expect(api.listProjects).toHaveBeenCalled());
    await user.type(screen.getByPlaceholderText("@agent to chat, # files, or describe what to build..."), longPrompt);
    await user.click(screen.getByTitle("Start building"));
    await waitFor(() => expect(api.createProject).toHaveBeenCalledWith({
      name: longPrompt.slice(0, 50) + "...",
      description: longPrompt,
      stack: "static",
    }));
  });

  it("shows load error when listProjects fails", async () => {
    vi.mocked(api.listProjects).mockRejectedValueOnce(new Error("fail"));
    render(<DashboardPage />);
    await waitForSignedIn();
    expect(await screen.findByText("Unable to load projects. Please try again later.")).toBeInTheDocument();
  });

  it("shows an empty state when the user has no projects", async () => {
    vi.mocked(api.listProjects).mockResolvedValueOnce([]);
    render(<DashboardPage />);
    await waitForSignedIn();
    expect(await screen.findByRole("heading", { name: "No projects yet" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Browse templates" })).toHaveAttribute("href", "/templates");
  });

  it("renders templates loading, data, fallback icon, and error state", async () => {
    vi.mocked(api.listTemplates).mockResolvedValueOnce([templateFixture, { ...templateFixture, id: "x", icon: "unknown", name: "Fallback" }]);
    const { unmount } = render(<TemplatesPage />);
    expect(document.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
    expect(await screen.findByText("SaaS App")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /Use Template/ })[0]).toHaveAttribute("href", "/dashboard?template=saas");
    expect(screen.getByText("Fallback")).toBeInTheDocument();

    vi.mocked(api.listTemplates).mockRejectedValueOnce(new Error("fail"));
    unmount();
    render(<TemplatesPage />);
    expect(await screen.findByText("Unable to load templates. Please try again later.")).toBeInTheDocument();
  });

  it("autostarts build without changing mode when no mode is provided", async () => {
    setMockParams({ id: "project-1" });
    window.history.pushState({}, "", "/project/project-1?autostart=true");
    render(<ProjectWorkspace />);
    await waitForSignedIn();
    await waitFor(() => expect(websocketMocks.startBuild).toHaveBeenCalledWith("Build a test app"));
    expect(useProjectStore.getState().buildMode).toBe("team");
  });

  it("autostarts build with mode from URL search params", async () => {
    setMockParams({ id: "project-1" });
    window.history.pushState({}, "", "/project/project-1?autostart=true&mode=goal");
    render(<ProjectWorkspace />);
    await waitForSignedIn();
    await waitFor(() => expect(websocketMocks.startBuild).toHaveBeenCalledWith("Build a test app"));
    expect(useProjectStore.getState().buildMode).toBe("goal");
  });

  it("skips autostart when the project session already started", async () => {
    setMockParams({ id: "project-1" });
    sessionStorage.setItem("neutron-autostart:project-1", "1");
    window.history.pushState({}, "", "/project/project-1?autostart=true");
    render(<ProjectWorkspace />);
    await waitForSignedIn();
    await waitFor(() => expect(useProjectStore.getState().projectStatus).toBe("created"));
    expect(websocketMocks.startBuild).not.toHaveBeenCalled();
  });

  it("autostarts only once per project session", async () => {
    setMockParams({ id: "project-1" });
    window.history.pushState({}, "", "/project/project-1?autostart=true");
    const { unmount } = render(<ProjectWorkspace />);
    await waitForSignedIn();
    await waitFor(() => expect(websocketMocks.startBuild).toHaveBeenCalledTimes(1));

    unmount();
    websocketMocks.startBuild.mockClear();
    render(<ProjectWorkspace />);
    await waitForSignedIn();
    await waitFor(() => expect(useProjectStore.getState().projectStatus).toBe("created"));
    expect(websocketMocks.startBuild).not.toHaveBeenCalled();
  });

  it("waits for auth before loading workspace data", async () => {
    setMockParams({ id: "project-1" });
    useAuthStore.setState({
      user: null,
      loading: true,
      error: null,
      refreshMe: async () => {},
    });
    render(<ProjectWorkspace />);
    expect(api.getProject).not.toHaveBeenCalled();

    useAuthStore.setState({ user: testUser, loading: false });
    await waitFor(() => expect(api.getProject).toHaveBeenCalledWith("project-1"));
  });

  it("shows a login prompt on workspace when signed out", async () => {
    setMockParams({ id: "project-1" });
    seedSignedOutAuth();
    render(<ProjectWorkspace />);

    expect(await screen.findByRole("heading", { name: "Log in to open this workspace." })).toBeInTheDocument();
    await waitFor(() => expect(useAuthStore.getState().user).toBeNull());
    expect(api.getProject).not.toHaveBeenCalled();
    expect(websocketMocks.startBuild).not.toHaveBeenCalled();
  });

  it("renders project workspace loading, not found, and loaded states", async () => {
    setMockParams({ id: "project-1" });
    vi.mocked(api.getProject).mockResolvedValueOnce({ ...projectFixture, status: "building" });
    vi.mocked(api.getProjectCheckpoints).mockResolvedValueOnce({
      checkpoints: [{ id: "cp-1", created_at: "2026-01-01", parent_id: "", branch: "main", location: "db#cp-1" }],
      latest: "db#cp-1",
    });
    const { unmount } = render(<ProjectWorkspace />);
    await waitForSignedIn();
    expect(await screen.findByText("System ready")).toBeInTheDocument();
    expect(useProjectStore.getState().latestCheckpoint).toBe("db#cp-1");
    expect(useProjectStore.getState().files).toEqual([fileFixture]);
    expect(useProjectStore.getState().messages[0]).toMatchObject({ id: "m1", timestamp: new Date("2026-01-02T00:00:00.000Z").getTime() });
    await userEvent.type(screen.getByPlaceholderText("Send a message..."), "hello");
    await userEvent.click(screen.getByRole("button", { name: "Send message" }));
    expect(websocketMocks.send).toHaveBeenCalledWith({ type: "message", content: "hello" });
    const storeMessages = useProjectStore.getState().messages;
    expect(storeMessages[storeMessages.length - 1]).toMatchObject({ role: "user", content: "hello" });

    act(() => {
      window.dispatchEvent(
        new MessageEvent("message", {
          origin: "null",
          data: { source: "neutron-preview", type: "console", level: "error", message: "Boom" },
        })
      );
    });
    await userEvent.click(screen.getByRole("button", { name: /Console/ }));
    await userEvent.hover(screen.getByText("Boom"));
    await userEvent.click(screen.getByRole("button", { name: /Resolve/ }));
    expect(websocketMocks.send).toHaveBeenLastCalledWith({
      type: "message",
      content: '@engineer Fix this console error in the generated code: "Boom". Update the relevant files with write_code_file.',
      target_agent: "engineer",
    });

    vi.mocked(api.getProject).mockRejectedValueOnce(new Error("Project not found"));
    unmount();
    render(<ProjectWorkspace />);
    expect(await screen.findByRole("heading", { name: "Project not found" })).toBeInTheDocument();

    vi.mocked(api.getProject).mockRejectedValueOnce(new Error("Authentication required."));
    unmount();
    render(<ProjectWorkspace />);
    expect(await screen.findByRole("heading", { name: "Session expired" })).toBeInTheDocument();

    vi.mocked(api.getProject).mockRejectedValueOnce(new Error("Server unavailable"));
    unmount();
    render(<ProjectWorkspace />);
    expect(await screen.findByRole("heading", { name: "Could not load project" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));

    vi.mocked(api.getProject).mockRejectedValueOnce("network down");
    unmount();
    render(<ProjectWorkspace />);
    expect(await screen.findByRole("heading", { name: "Could not load project" })).toBeInTheDocument();
  });

  it("sends completed-project engineer mentions with an explicit target", async () => {
    setMockParams({ id: "project-1" });
    vi.mocked(api.getProject).mockResolvedValueOnce({ ...projectFixture, status: "complete" });
    render(<ProjectWorkspace />);
    await waitForSignedIn();

    const input = await screen.findByPlaceholderText("Describe an update, or type @ for Kai, Nina, Theo, Zara, or Ravi...");
    await userEvent.type(input, "@engineer add a filter");
    await userEvent.click(screen.getByRole("button", { name: "Send message" }));

    expect(websocketMocks.send).toHaveBeenCalledWith({
      type: "message",
      content: "@engineer add a filter",
      target_agent: "engineer",
    });
  });

  it("rehydrates structured phase result cards after refresh", async () => {
    setMockParams({ id: "project-1" });
    vi.mocked(api.getProject).mockResolvedValueOnce({ ...projectFixture, status: "complete" });
    vi.mocked(api.getProjectMessages).mockResolvedValueOnce([
      {
        id: 10,
        role: "user",
        content: "Build a fraud ops console",
        created_at: "2026-01-02T00:00:00.000Z",
      },
      {
        id: 11,
        role: "agent",
        agent: "team_leader",
        content: "A clear fraud ops brief.",
        created_at: "2026-01-02T00:01:00.000Z",
        kind: "phase_result",
        metadata: {
          phase: "leading",
          kind: "brief",
          headline: "FraudOps brief",
          summary: "A clear fraud ops brief.",
          spec: { mvp_inclusions: ["Alert queue", "Metrics"] },
          has_structured_spec: true,
        },
      },
      {
        id: 12,
        role: "agent",
        agent: "engineer",
        content: "Wrote the project files.",
        created_at: "2026-01-02T00:05:00.000Z",
        kind: "phase_result",
        metadata: {
          phase: "building",
          kind: "not-a-real-kind",
          headline: "Project files ready",
          summary: "Wrote the project files.",
          has_structured_spec: false,
        },
      },
    ] as never);
    render(<ProjectWorkspace />);
    await waitForSignedIn();

    await waitFor(() => {
      const hydrated = useProjectStore.getState().messages;
      expect(hydrated).toHaveLength(3);
    });

    const hydrated = useProjectStore.getState().messages;
    expect(hydrated[0]).toMatchObject({ role: "user", content: "Build a fraud ops console" });
    expect(hydrated[1]).toMatchObject({
      kind: "phase_result",
      phaseResult: {
        kind: "brief",
        headline: "FraudOps brief",
        summary: "A clear fraud ops brief.",
        hasStructuredSpec: true,
      },
    });
    expect(hydrated[2]).toMatchObject({
      kind: "phase_result",
      // Unknown API kinds coerce to markdown so PhaseResultCard still renders.
      phaseResult: {
        kind: "markdown",
        headline: "Project files ready",
        summary: "Wrote the project files.",
      },
    });
    expect(await screen.findByText("FraudOps brief")).toBeInTheDocument();
    expect(screen.getByText("Brief")).toBeInTheDocument();
  });

  it("loads workspace when checkpoint listing fails", async () => {
    setMockParams({ id: "project-1" });
    vi.mocked(api.getProjectCheckpoints).mockRejectedValueOnce(new Error("checkpoint unavailable"));
    render(<ProjectWorkspace />);
    await waitForSignedIn();
    expect(await screen.findByText("System ready")).toBeInTheDocument();
    expect(useProjectStore.getState().latestCheckpoint).toBeNull();
  });
});
