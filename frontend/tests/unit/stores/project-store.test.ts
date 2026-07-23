import { beforeEach, describe, expect, it, vi } from "vitest";
import { useProjectStore } from "@/stores/project-store";
import type { AgentName } from "@/types";

describe("project-store", () => {
  beforeEach(() => {
    useProjectStore.getState().reset();
    vi.spyOn(globalThis.crypto, "randomUUID").mockReturnValue("uuid-1" as `${string}-${string}-${string}-${string}-${string}`);
    vi.spyOn(Date, "now").mockReturnValue(1234);
  });

  it("starts with the initial runtime state", () => {
    expect(useProjectStore.getState()).toMatchObject({
      messages: [],
      agents: [
        { agent: "team_leader", status: "idle" },
        { agent: "product_manager", status: "idle" },
        { agent: "architect", status: "idle" },
        { agent: "engineer", status: "idle" },
        { agent: "data_scientist", status: "idle" },
      ],
      files: [],
      projectStatus: "created",
      currentPhase: "",
      pendingFeedback: null,
    });
  });

  it("adds deterministic messages in order", () => {
    useProjectStore.getState().addMessage({ role: "user", content: "hello" });
    useProjectStore.getState().addMessage({ role: "system", content: "done" });

    expect(useProjectStore.getState().messages).toEqual([
      { id: "uuid-1", timestamp: 1234, role: "user", content: "hello" },
      { id: "uuid-1", timestamp: 1234, role: "system", content: "done" },
    ]);
  });

  it("updates one agent and preserves or overrides currentTask", () => {
    const store = useProjectStore.getState();
    store.updateAgent("engineer", "working", "Build UI");
    store.updateAgent("engineer", "complete");
    store.updateAgent("engineer", "thinking", "");
    store.updateAgent("missing" as AgentName, "working", "No-op");

    const engineer = useProjectStore.getState().agents.find((agent) => agent.agent === "engineer");
    const leader = useProjectStore.getState().agents.find((agent) => agent.agent === "team_leader");
    expect(engineer).toEqual({ agent: "engineer", status: "thinking", currentTask: "" });
    expect(leader).toEqual({ agent: "team_leader", status: "idle" });
  });

  it("upserts files and moves replacements to the end", () => {
    const store = useProjectStore.getState();
    store.addFile({ file_path: "a.ts", content: "one" });
    store.addFile({ file_path: "b.ts", content: "two" });
    store.addFile({ file_path: "a.ts", content: "three" });

    expect(useProjectStore.getState().files).toEqual([
      { file_path: "b.ts", content: "two" },
      { file_path: "a.ts", content: "three" },
    ]);
  });

  it("sets direct values and resets all state", () => {
    const messages = [{ id: "m1", role: "agent" as const, agent: "engineer" as const, content: "hi", timestamp: 1 }];
    const files = [{ file_path: "index.html", content: "<h1 />" }];
    const feedback = { phase: "building", agent: "engineer" as const, content: "mock", message: "review" };
    const store = useProjectStore.getState();

    store.setMessages(messages);
    store.setFiles(files);
    // Internal metadata is stripped from the workspace file list.
    store.setFiles([
      ...files,
      { file_path: "connectors.json", content: "{}" },
    ]);
    store.setProjectStatus("awaiting_feedback");
    store.setPhase("building");
    store.setPendingFeedback(feedback);

    expect(useProjectStore.getState().messages).toBe(messages);
    expect(useProjectStore.getState().files).toEqual(files);
    expect(useProjectStore.getState().files.some((f) => f.file_path === "connectors.json")).toBe(false);
    expect(useProjectStore.getState()).toMatchObject({
      projectStatus: "awaiting_feedback",
      currentPhase: "building",
      pendingFeedback: feedback,
    });

    store.updateAgent("engineer", "complete");
    store.resetAgents();
    expect(useProjectStore.getState().agents.find(a => a.agent === "engineer")?.status).toBe("idle");

    store.reset();
    expect(useProjectStore.getState()).toMatchObject({
      messages: [],
      files: [],
      projectStatus: "created",
      currentPhase: "",
      pendingFeedback: null,
    });
    expect(useProjectStore.getState().thinkingMessages.size).toBe(0);
  });

  it("sets and clears thinking messages", () => {
    const store = useProjectStore.getState();
    store.setThinking("engineer", "Processing...");
    expect(useProjectStore.getState().thinkingMessages.get("engineer")).toMatchObject({
      agent: "engineer",
      content: "Processing...",
    });

    store.setThinking("architect", "Designing...");
    expect(useProjectStore.getState().thinkingMessages.size).toBe(2);

    store.clearThinking("engineer");
    expect(useProjectStore.getState().thinkingMessages.has("engineer")).toBe(false);
    expect(useProjectStore.getState().thinkingMessages.has("architect")).toBe(true);

    store.clearThinking("architect");
    expect(useProjectStore.getState().thinkingMessages.size).toBe(0);
  });

  it("appends live thinking stream and stores phase results as cards", () => {
    const store = useProjectStore.getState();
    store.appendThinkingStream("engineer", "", "Ignored empty");
    store.appendThinkingStream("architect", "solo");
    expect(useProjectStore.getState().thinkingMessages.get("architect")).toMatchObject({
      content: "Working...",
      stream: "solo",
    });
    store.appendThinkingStream("engineer", "First ", "Coding");
    store.appendThinkingStream("engineer", "chunk");
    expect(useProjectStore.getState().thinkingMessages.get("engineer")).toMatchObject({
      agent: "engineer",
      content: "Coding",
      stream: "First chunk",
    });

    store.addPhaseResult({
      phase: "planning",
      agent: "product_manager",
      kind: "plan",
      headline: "Portfolio plan",
      summary: "A focused MVP plan.",
      spec: { mvp_features: ["Hero"] },
      hasStructuredSpec: true,
    });

    const state = useProjectStore.getState();
    expect(state.phaseResults).toHaveLength(1);
    expect(state.messages.at(-1)).toMatchObject({
      kind: "phase_result",
      agent: "product_manager",
      content: "A focused MVP plan.",
    });
    expect(state.messages.at(-1)?.phaseResult?.headline).toBe("Portfolio plan");
  });

  it("includes thinkingMessages in reset", () => {
    const store = useProjectStore.getState();
    store.setThinking("engineer", "Working...");
    store.addPhaseResult({
      phase: "building",
      agent: "engineer",
      kind: "build",
      headline: "Done",
      summary: "Built.",
      hasStructuredSpec: false,
    });
    store.reset();
    expect(useProjectStore.getState().thinkingMessages.size).toBe(0);
    expect(useProjectStore.getState().phaseResults).toEqual([]);
  });

  it("sets and clears token usage", () => {
    const store = useProjectStore.getState();
    expect(store.tokenUsage).toBeNull();
    store.setTokenUsage({ total_tokens: 100, prompt_tokens: 60, completion_tokens: 40, successful_requests: 2 });
    expect(useProjectStore.getState().tokenUsage).toEqual({ total_tokens: 100, prompt_tokens: 60, completion_tokens: 40, successful_requests: 2 });
    store.setTokenUsage(null);
    expect(useProjectStore.getState().tokenUsage).toBeNull();
  });

  it("includes tokenUsage in reset", () => {
    const store = useProjectStore.getState();
    store.setTokenUsage({ total_tokens: 100, prompt_tokens: 60, completion_tokens: 40, successful_requests: 2 });
    store.reset();
    expect(useProjectStore.getState().tokenUsage).toBeNull();
  });

  it("tracks latest checkpoint state", () => {
    const store = useProjectStore.getState();
    store.setLatestCheckpoint("db#saved");
    expect(useProjectStore.getState().latestCheckpoint).toBe("db#saved");
    store.reset();
    expect(useProjectStore.getState().latestCheckpoint).toBeNull();
  });

  it("tracks token budgets, phase progress, and bounded build activity", () => {
    const store = useProjectStore.getState();
    store.setTokenBudget(20_000);
    store.setPhasePercent(120);
    expect(useProjectStore.getState()).toMatchObject({ tokenBudget: 20_000, phasePercent: 100 });
    store.setPhasePercent(-10);
    expect(useProjectStore.getState().phasePercent).toBe(0);
    store.setPhasePercent(null);

    store.addActivity({ kind: "phase", title: "Plan", status: "active" });
    store.addActivity({ kind: "tool", title: "Read file", status: "active" });
    store.completeActiveActivities("tool");
    expect(useProjectStore.getState().activities).toEqual([
      expect.objectContaining({ kind: "phase", status: "active", id: "uuid-1", timestamp: 1234 }),
      expect.objectContaining({ kind: "tool", status: "complete", id: "uuid-1", timestamp: 1234 }),
    ]);
    store.completeActiveActivities();
    expect(useProjectStore.getState().activities.every((activity) => activity.status === "complete")).toBe(true);

    store.addActivity({ kind: "tool", title: "Writing a project file", status: "active" });
    store.finishActiveActivities("tool", "error", {
      summary: "Failed: path escapes project",
      title: "Writing a project file",
    });
    expect(useProjectStore.getState().activities.at(-1)).toEqual(
      expect.objectContaining({
        kind: "tool",
        status: "error",
        summary: "Failed: path escapes project",
        title: "Writing a project file",
      }),
    );

    store.addActivity({
      kind: "tool",
      title: "Read File",
      summary: "original",
      details: "args",
      status: "active",
      durationMs: 10,
    });
    store.finishActiveActivities("tool", "complete", {});
    expect(useProjectStore.getState().activities.at(-1)).toEqual(
      expect.objectContaining({
        title: "Read File",
        summary: "original",
        details: "args",
        durationMs: 10,
        status: "complete",
      }),
    );

    for (let index = 0; index < 101; index += 1) {
      store.addActivity({ kind: "file", title: `File ${index}`, status: "complete" });
    }
    expect(useProjectStore.getState().activities).toHaveLength(100);
    store.reset();
    expect(useProjectStore.getState()).toMatchObject({ tokenBudget: null, phasePercent: null, activities: [] });
  });
});
