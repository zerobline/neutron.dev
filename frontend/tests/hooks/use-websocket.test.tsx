import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { refreshProjectFiles, useProjectWebSocket } from "@/hooks/use-websocket";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectStore } from "@/stores/project-store";
import type { ProjectStatus } from "@/types";
import { MockWebSocket } from "../mocks/websocket";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getProjectFiles: vi.fn(),
    },
  };
});

const testUser = { id: "user-1", email: "user@example.com", display_name: null, created_at: "2026-01-01" };

describe("useProjectWebSocket", () => {
  beforeEach(async () => {
    useAuthStore.setState({ user: testUser, loading: false, error: null });
    const { api } = await import("@/lib/api");
    vi.mocked(api.getProjectFiles).mockReset();
  });
  it("refreshes project files after completion and ignores failures", async () => {
    const { api } = await import("@/lib/api");
    vi.mocked(api.getProjectFiles).mockResolvedValue([
      { file_path: "index.html", content: "<html></html>" },
    ]);

    await refreshProjectFiles("p1");
    expect(useProjectStore.getState().files).toEqual([
      { file_path: "index.html", content: "<html></html>" },
    ]);

    await refreshProjectFiles(null);
    vi.mocked(api.getProjectFiles).mockRejectedValue(new Error("offline"));
    await refreshProjectFiles("p1");
    expect(api.getProjectFiles).toHaveBeenCalledTimes(2);
  });

  it("does not connect without a project id", () => {
    useAuthStore.setState({ user: testUser, loading: false, error: null });
    const { result } = renderHook(() => useProjectWebSocket(null));
    expect(MockWebSocket.instances).toHaveLength(0);
    expect(result.current.connected).toBe(false);
  });

  it("connects, sends only when open, reports connected, and cleans up", () => {
    const { result, unmount } = renderHook(() => useProjectWebSocket("p1"));
    const ws = MockWebSocket.instances[0];
    expect(ws.url).toBe("ws://localhost:8000/ws/project/p1");

    act(() => result.current.send({ type: "message" }));
    expect(ws.send).not.toHaveBeenCalled();

    act(() => ws.open());
    expect(result.current.connected).toBe(true);

    act(() => result.current.send({ type: "message", content: "hello" }));
    expect(ws.send).toHaveBeenCalledWith(JSON.stringify({ type: "message", content: "hello" }));

    act(() => ws.error());
    expect(result.current.connected).toBe(false);
    act(() => ws.open());
    act(() => ws.close());
    expect(result.current.connected).toBe(false);

    unmount();
    expect(ws.close).toHaveBeenCalled();
  });

  it("reconnects when project id changes", () => {
    const { rerender } = renderHook(({ id }) => useProjectWebSocket(id), { initialProps: { id: "p1" } });
    const first = MockWebSocket.instances[0];
    rerender({ id: "p2" });
    expect(first.close).toHaveBeenCalled();
    expect(MockWebSocket.instances[1].url).toBe("ws://localhost:8000/ws/project/p2");
  });

  it("starts builds with connector payloads and sends feedback", () => {
    localStorage.setItem("neutron-custom-mcp-servers", JSON.stringify([
      { id: "remote", name: "Remote", transport: "http", commandOrUrl: "https://example.com/mcp", notes: "docs", createdAt: "2026-01-01", updatedAt: "2026-01-01" },
    ]));
    const { result } = renderHook(() => useProjectWebSocket("p1"));
    const ws = MockWebSocket.instances[0];
    act(() => ws.open());

    act(() => result.current.startBuild("Build it"));
    act(() => result.current.sendFeedback("revise", "Change color"));
    act(() => result.current.sendFeedback("approve"));

    expect(useProjectStore.getState().messages.at(-1)).toMatchObject({ role: "user", content: "Build it" });
    const startPayload = JSON.parse(ws.sent[0] as string) as {
      type: string;
      prompt: string;
      mode: string;
      connectors: { custom_mcp_servers: unknown[]; default_mcps: unknown[] };
    };
    expect(startPayload).toMatchObject({
      type: "start_build",
      prompt: "Build it",
      mode: "team",
    });
    expect(startPayload.connectors.custom_mcp_servers).toEqual([
      { id: "remote", name: "Remote", transport: "http", command_or_url: "https://example.com/mcp", notes: "docs" },
    ]);
    expect(startPayload.connectors.default_mcps?.length).toBeGreaterThan(0);
    expect(ws.sent).toContain(JSON.stringify({ type: "human_feedback", action: "revise", feedback: "Change color" }));
    expect(ws.sent).toContain(JSON.stringify({ type: "human_feedback", action: "approve", feedback: "" }));
  });

  it("resumes and forks builds with checkpoint payloads", () => {
    localStorage.clear();
    useProjectStore.setState({ latestCheckpoint: "db#saved" });
    const { result } = renderHook(() => useProjectWebSocket("p1"));
    const ws = MockWebSocket.instances[0];
    expect(ws).toBeDefined();
    act(() => ws.open());

    act(() => result.current.resumeBuild("Build it"));
    act(() => result.current.forkBuild("Build it", "db#fork", "experiment-a"));
    useProjectStore.setState({ latestCheckpoint: null });
    act(() => result.current.resumeBuild("Retry", null));
    act(() => result.current.forkBuild("Branch", null));

    const payloads = ws.sent.map((item) => JSON.parse(item as string) as Record<string, unknown>);
    expect(payloads).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          type: "resume_build",
          prompt: "Build it",
          mode: "team",
          checkpoint: "db#saved",
        }),
        expect.objectContaining({
          type: "fork_build",
          prompt: "Build it",
          mode: "team",
          checkpoint: "db#fork",
          branch: "experiment-a",
        }),
        expect.objectContaining({
          type: "resume_build",
          prompt: "Retry",
          mode: "team",
        }),
        expect.objectContaining({
          type: "fork_build",
          prompt: "Branch",
          mode: "team",
        }),
      ]),
    );
  });

  it("does not connect without a signed-in user", () => {
    useAuthStore.setState({ user: null, loading: false, error: null });
    const { result } = renderHook(() => useProjectWebSocket("p1"));
    expect(MockWebSocket.instances).toHaveLength(0);
    expect(result.current.connected).toBe(false);
  });

  it("handles websocket events and missing fields", async () => {
    renderHook(() => useProjectWebSocket("p1"));
    const ws = MockWebSocket.instances[0];

    act(() => ws.message({ type: "phase_start", phase: "leading", message: "Leading" }));
    act(() => ws.message({ type: "phase_start", phase: "leading", usage: { total_tokens: 10, prompt_tokens: 6, completion_tokens: 4, successful_requests: 1 }, token_budget: 100 }));
    expect(useProjectStore.getState()).toMatchObject({ currentPhase: "leading", projectStatus: "leading" });
    act(() => ws.message({ type: "phase_start", phase: "analyzing" }));
    act(() => ws.message({ type: "phase_start", phase: "planning" }));
    act(() => ws.message({ type: "phase_start", phase: "architecting" }));
    act(() => ws.message({ type: "phase_start", phase: "building" }));
    act(() => ws.message({ type: "phase_start", phase: "unknown" }));
    act(() => ws.message({ type: "phase_start" }));
    expect(useProjectStore.getState().currentPhase).toBe("");

    act(() => ws.message({ type: "agent_start", agent: "engineer", task: "Code" }));
    act(() => ws.message({ type: "agent_start", agent: "team_leader" }));
    act(() => ws.message({ type: "stream_chunk", agent: "team_leader", content: " first chunk" }));
    act(() => ws.message({ type: "agent_start" }));
    act(() => ws.message({ type: "agent_thinking", agent: "engineer", content: "Thinking" }));
    act(() => ws.message({ type: "agent_thinking", agent: "architect" }));
    act(() => ws.message({ type: "agent_thinking" }));
    expect(useProjectStore.getState().thinkingMessages.get("engineer")).toMatchObject({ agent: "engineer", content: "Code" });
    act(() => ws.message({ type: "stream_chunk", agent: "engineer", content: " token" }));
    expect(useProjectStore.getState().thinkingMessages.get("engineer")?.content).toBe("Code");
    expect(useProjectStore.getState().thinkingMessages.get("engineer")?.stream).toContain("token");
    act(() => ws.message({ type: "stream_chunk", agent: "product_manager", content: '{"headline":' }));
    expect(useProjectStore.getState().thinkingMessages.get("product_manager")?.stream ?? "").toBe("");
    act(() => ws.message({ type: "stream_chunk", agent: "engineer" }));
    act(() => ws.message({ type: "stream_chunk", content: "ignored" }));
    act(() => ws.message({ type: "tool_call", agent: "engineer", tool_name: "write_code_file", content: "Calling write_code_file..." }));
    // Stream while a tool is still active should auto-complete the tool row.
    act(() => ws.message({ type: "stream_chunk", agent: "engineer", content: " mid tool " }));
    expect(
      useProjectStore
        .getState()
        .activities.some((item) => item.kind === "tool" && item.status === "complete"),
    ).toBe(true);
    act(() => ws.message({ type: "tool_call", agent: "engineer", tool_name: "write_code_file", content: "Calling write_code_file..." }));
    act(() => ws.message({ type: "tool_call", agent: "engineer" }));
    act(() =>
      ws.message({
        type: "tool_result",
        agent: "engineer",
        tool_name: "write_code_file",
        status: "complete",
        content: "Successfully wrote 120 bytes to index.html",
        duration_ms: 842,
      }),
    );
    expect(
      useProjectStore
        .getState()
        .activities.some(
          (item) =>
            item.kind === "tool" &&
            item.status === "complete" &&
            item.summary?.includes("120 bytes") &&
            item.durationMs === 842,
        ),
    ).toBe(true);
    act(() =>
      ws.message({
        type: "tool_result",
        agent: "engineer",
        tool_name: "read_file",
        status: "error",
        content: "Failed: missing file",
      }),
    );
    expect(
      useProjectStore
        .getState()
        .activities.some((item) => item.kind === "tool" && item.status === "error"),
    ).toBe(true);
    act(() =>
      ws.message({
        type: "agent_step",
        agent: "engineer",
        title: "Composing structured output",
        content: "Drafting the phase result…",
        status: "active",
      }),
    );
    act(() =>
      ws.message({
        type: "agent_step",
        agent: "engineer",
        title: "x".repeat(90),
        content: "Short label",
        status: "error",
      }),
    );
    act(() =>
      ws.message({
        type: "agent_step",
        agent: "engineer",
        title: '{"headline":"x"}',
        content: '{"summary":"y"}',
        status: "complete",
      }),
    );
    act(() =>
      ws.message({
        type: "agent_step",
        agent: "engineer",
        status: "active",
      }),
    );
    expect(
      useProjectStore
        .getState()
        .activities.some((item) => item.kind === "step" && item.title.includes("structured")),
    ).toBe(true);
    act(() => ws.message({ type: "stream_chunk", agent: "engineer", content: " after tool" }));
    act(() => ws.message({ type: "agent_start", agent: "architect", task: "Inspect" }));
    act(() => ws.message({ type: "stream_chunk", agent: "architect", content: " first chunk" }));
    act(() => ws.message({ type: "tool_call", agent: "architect", tool_name: "read_file" }));
    act(() => ws.message({ type: "tool_call" }));
    act(() => ws.message({ type: "checkpoint_resume" }));
    act(() => ws.message({ type: "checkpoint_resume", message: "Resuming without checkpoint id" }));
    act(() => ws.message({ type: "checkpoint_resume", checkpoint: "db#only" }));
    expect(useProjectStore.getState().messages.some((m) => m.kind === "thinking")).toBe(false);
    expect(useProjectStore.getState().activities.some((item) => item.kind === "tool" && item.title === "Writing a project file")).toBe(true);
    act(() => ws.message({ type: "agent_thinking", agent: "engineer" }));
    act(() => ws.message({ type: "agent_complete", agent: "engineer", content: "Done" }));
    expect(useProjectStore.getState().thinkingMessages.has("engineer")).toBe(false);
    expect(useProjectStore.getState().messages.some((m) => m.content === "Done")).toBe(false);
    act(() => ws.message({
      type: "phase_result",
      agent: "engineer",
      phase: "building",
      kind: "build",
      headline: "Files ready",
      summary: "Wrote the root project files.",
      has_structured_spec: true,
      spec: { files_written: ["index.html"] },
    }));
    expect(useProjectStore.getState().messages.some((m) => m.kind === "phase_result")).toBe(true);
    act(() => ws.message({
      type: "phase_result",
      agent: "team_leader",
      phase: "leading",
      kind: "brief",
      headline: '{"headline":"Admin Dashboard","summary":"Build an admin UI."}',
      summary: '{"headline":"Admin Dashboard","summary":"Build an admin UI."}',
      has_structured_spec: false,
    }));
    const leaderCard = useProjectStore.getState().messages.find(
      (message) => message.agent === "team_leader" && message.kind === "phase_result",
    );
    expect(leaderCard?.phaseResult?.headline).toBe("Admin Dashboard");
    expect(leaderCard?.phaseResult?.summary).toBe("Build an admin UI.");
    act(() => ws.message({ type: "agent_complete", agent: "team_leader" }));
    act(() => ws.message({ type: "agent_complete" }));
    act(() => ws.message({ type: "phase_result" }));
    act(() => ws.message({ type: "agent_routed", agent: "engineer", message: "Ravi is handling the edit." }));
    expect(useProjectStore.getState().messages.at(-1)?.content).toBe("Ravi is handling the edit.");
    act(() => ws.message({ type: "agent_routed", agent: "engineer" }));
    act(() => ws.message({ type: "agent_routed" }));

    act(() => ws.message({ type: "file_created", file_path: "index.html", content: "<html></html>" }));
    act(() => ws.message({ type: "file_created", file_path: "style.css" }));
    act(() => ws.message({ type: "file_created" }));
    expect(useProjectStore.getState().files).toEqual([
      { file_path: "index.html", content: "<html></html>" },
      { file_path: "style.css", content: "" },
    ]);

    const { api } = await import("@/lib/api");
    vi.mocked(api.getProjectFiles).mockResolvedValue([
      { file_path: "index.html", content: "<html></html>" },
      { file_path: "styles.css", content: "body{}" },
      { file_path: "app.js", content: "init()" },
    ]);

    act(() =>
      ws.message({
        type: "project_complete",
        message: "Project generation complete!",
        mode: "team",
        files: ["index.html", "styles.css", "app.js"],
        files_changed: ["index.html", "styles.css", "app.js"],
        checklist: {
          required_files: true,
          seeded_demo_data: false,
          items: [
            { id: "required_files", label: "Core files written", ok: true },
            { id: "seeded_demo_data", label: "Demo data seeded", ok: false },
          ],
        },
        suggestions: [
          { id: "mock_data", label: "Fill with mock data", prompt: "@engineer Fill with mock data" },
        ],
      }),
    );
    expect(useProjectStore.getState().projectStatus).toBe("complete");
    expect(useProjectStore.getState().lastCompletion?.suggestions[0]?.id).toBe("mock_data");
    expect(useProjectStore.getState().lastCompletion?.filesChanged).toContain("app.js");
    expect(useProjectStore.getState().tokenUsage?.total_tokens).toBe(10);
    await waitFor(() => {
      expect(api.getProjectFiles).toHaveBeenCalledWith("p1");
      expect(useProjectStore.getState().files).toEqual([
        { file_path: "index.html", content: "<html></html>" },
        { file_path: "styles.css", content: "body{}" },
        { file_path: "app.js", content: "init()" },
      ]);
    });
    useProjectStore.getState().setProjectStatus("building" as ProjectStatus);
    act(() => ws.message({ type: "project_complete", usage: { total_tokens: 500, prompt_tokens: 300, completion_tokens: 200, successful_requests: 3 } }));
    expect(useProjectStore.getState().tokenUsage).toEqual({ total_tokens: 500, prompt_tokens: 300, completion_tokens: 200, successful_requests: 3 });
    useProjectStore.getState().setPhasePercent(null);
    act(() => ws.message({ type: "token_usage", usage: { total_tokens: 700, prompt_tokens: 400, completion_tokens: 300, successful_requests: 4 }, token_budget: 1000, percent: 75 }));
    expect(useProjectStore.getState()).toMatchObject({ tokenBudget: 1000, phasePercent: null });
    act(() => ws.message({ type: "usage_update", usage: { total_tokens: 800, prompt_tokens: 450, completion_tokens: 350, successful_requests: 5 } }));
    act(() => ws.message({ type: "usage_update", token_budget: 0 }));
    expect(useProjectStore.getState().tokenUsage?.total_tokens).toBe(800);
    act(() => ws.message({ type: "human_feedback_request", phase: "building", agent: "engineer", content: "Mock", message: "Review" }));
    expect(useProjectStore.getState().pendingFeedback).toEqual({
      phase: "building",
      agent: "engineer",
      content: "Mock",
      message: "Review",
      summary: "Mock",
      headline: undefined,
      kind: undefined,
      spec: null,
    });
    act(() => ws.message({ type: "human_feedback_request" }));
    expect(useProjectStore.getState().pendingFeedback).toEqual({
      phase: "",
      agent: "team_leader",
      content: "",
      message: "Review output before proceeding",
      summary: undefined,
      headline: undefined,
      kind: undefined,
      spec: null,
    });
    act(() => ws.message({ type: "human_feedback_response", action: "approve" }));
    expect(useProjectStore.getState().pendingFeedback).toBeNull();
    act(() => ws.message({ type: "human_feedback_response", action: "revise", feedback: "Again" }));
    act(() => ws.message({ type: "human_feedback_response", action: "revise" }));
    act(() => ws.message({
      type: "feedback_error",
      category: "invalid_action",
      next_action: "Choose approve or revise",
      message: "Unsupported feedback action.",
    }));
    expect(useProjectStore.getState().messages.at(-1)).toMatchObject({
      kind: "error",
      category: "invalid_action",
      nextAction: "Choose approve or revise",
      content: "Unsupported feedback action.",
    });
    act(() => ws.message({ type: "feedback_error" }));
    expect(useProjectStore.getState().messages.at(-1)).toMatchObject({
      kind: "error",
      content: "Invalid feedback.",
    });
    act(() => ws.message({ type: "agent_thinking", agent: "product_manager", content: "Planning" }));
    act(() => ws.message({ type: "checkpoint_resume", checkpoint: "db#1", message: "Resuming" }));
    expect(useProjectStore.getState().latestCheckpoint).toBe("db#1");
    act(() => ws.message({ type: "error", agent: "product_manager", phase: "planning", category: "quota", message: "Quota hit", details: "limit", next_action: "Switch provider", checkpoint: "db#2", can_resume: true }));
    expect(useProjectStore.getState().projectStatus).toBe("error");
    expect(useProjectStore.getState().latestCheckpoint).toBe("db#2");
    expect(useProjectStore.getState().thinkingMessages.has("product_manager")).toBe(false);
    expect(useProjectStore.getState().agents.find((agent) => agent.agent === "product_manager")).toMatchObject({ status: "error", currentTask: "Failed during planning" });
    expect(useProjectStore.getState().messages.at(-1)).toMatchObject({ kind: "error", content: "Quota hit", category: "quota", details: "limit", nextAction: "Switch provider" });
    act(() => ws.message({ type: "error", agent: "architect", message: "Architect failed" }));
    expect(useProjectStore.getState().agents.find((agent) => agent.agent === "architect")).toMatchObject({
      status: "error",
    });
    act(() => ws.message({ type: "error" }));

    const before = useProjectStore.getState().messages.length;
    act(() => ws.message({ type: "unknown" }));
    act(() => ws.messageRaw("not json"));
    expect(useProjectStore.getState().messages.length).toBe(before + 1);
    expect(useProjectStore.getState().messages.at(-1)?.content).toBe("Received an invalid server message.");
  });
});
