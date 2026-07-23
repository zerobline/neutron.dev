import { create } from "zustand";
import type {
  Message,
  AgentStatus,
  ProjectFile,
  ProjectStatus,
  AgentName,
  AgentStatusType,
  FeedbackRequest,
  BuildMode,
  ThinkingMessage,
  TokenUsage,
  BuildActivity,
  PhaseResult,
  BuildCompletion,
  LastEditDiff,
  BuildStack,
} from "@/types";
import { filterWorkspaceFiles, isWorkspaceVisibleFile } from "@/lib/project-files";

interface ProjectStore {
  messages: Message[];
  agents: AgentStatus[];
  files: ProjectFile[];
  projectStatus: ProjectStatus;
  projectStack: BuildStack | string;
  currentPhase: string;
  pendingFeedback: FeedbackRequest | null;
  buildMode: BuildMode;
  thinkingMessages: Map<AgentName, ThinkingMessage>;
  phaseResults: PhaseResult[];
  tokenUsage: TokenUsage | null;
  tokenBudget: number | null;
  phasePercent: number | null;
  activities: BuildActivity[];
  lastCompletion: BuildCompletion | null;
  lastEditDiff: LastEditDiff | null;

  addMessage: (msg: Omit<Message, "id" | "timestamp">) => void;
  updateAgent: (agent: AgentName, status: AgentStatusType, task?: string) => void;
  addFile: (file: ProjectFile) => void;
  setMessages: (messages: Message[]) => void;
  setFiles: (files: ProjectFile[]) => void;
  setProjectStatus: (status: ProjectStatus) => void;
  setProjectStack: (stack: BuildStack | string) => void;
  setPhase: (phase: string) => void;
  setPendingFeedback: (req: FeedbackRequest | null) => void;
  setBuildMode: (mode: BuildMode) => void;
  setThinking: (agent: AgentName, content: string) => void;
  appendThinkingStream: (agent: AgentName, chunk: string, fallbackLabel?: string) => void;
  clearThinking: (agent: AgentName) => void;
  addPhaseResult: (result: Omit<PhaseResult, "id" | "timestamp">) => void;
  latestCheckpoint: string | null;
  setLatestCheckpoint: (checkpoint: string | null) => void;
  setTokenUsage: (usage: TokenUsage | null) => void;
  setTokenBudget: (budget: number | null) => void;
  setPhasePercent: (percent: number | null) => void;
  setLastCompletion: (completion: BuildCompletion | null) => void;
  setLastEditDiff: (diff: LastEditDiff | null) => void;
  addActivity: (activity: Omit<BuildActivity, "id" | "timestamp">) => void;
  completeActiveActivities: (kind?: BuildActivity["kind"]) => void;
  finishActiveActivities: (
    kind: BuildActivity["kind"] | undefined,
    status: BuildActivity["status"],
    patch?: Partial<Pick<BuildActivity, "summary" | "details" | "title" | "durationMs">>,
  ) => void;
  resetAgents: () => void;
  reset: () => void;
}

const initialAgents: AgentStatus[] = [
  { agent: "team_leader", status: "idle" },
  { agent: "product_manager", status: "idle" },
  { agent: "architect", status: "idle" },
  { agent: "engineer", status: "idle" },
  { agent: "data_scientist", status: "idle" },
];

const STREAM_LIMIT = 2400;

export const useProjectStore = create<ProjectStore>((set) => ({
  messages: [],
  agents: [...initialAgents],
  files: [],
  projectStatus: "created",
  projectStack: "static",
  currentPhase: "",
  pendingFeedback: null,
  buildMode: "team",
  thinkingMessages: new Map(),
  phaseResults: [],
  tokenUsage: null,
  tokenBudget: null,
  phasePercent: null,
  activities: [],
  lastCompletion: null,
  lastEditDiff: null,
  latestCheckpoint: null,

  addMessage: (msg) =>
    set((state) => ({
      messages: [
        ...state.messages,
        { ...msg, id: crypto.randomUUID(), timestamp: Date.now() },
      ],
    })),

  updateAgent: (agent, status, task) =>
    set((state) => ({
      agents: state.agents.map((a) =>
        a.agent === agent ? { ...a, status, currentTask: task ?? a.currentTask } : a
      ),
    })),

  addFile: (file) => {
    if (!isWorkspaceVisibleFile(file.file_path)) return;
    set((state) => ({
      files: [...state.files.filter((f) => f.file_path !== file.file_path), file],
    }));
  },

  setMessages: (messages) => set({ messages }),

  setFiles: (files) => set({ files: filterWorkspaceFiles(files) }),

  setProjectStatus: (status) => set({ projectStatus: status }),

  setProjectStack: (stack) => set({ projectStack: stack || "static" }),

  setPhase: (phase) => set({ currentPhase: phase }),

  setPendingFeedback: (req) => set({ pendingFeedback: req }),

  setBuildMode: (mode) => set({ buildMode: mode }),

  setThinking: (agent, content) =>
    set((state) => {
      const next = new Map(state.thinkingMessages);
      const existing = next.get(agent);
      next.set(agent, {
        agent,
        content,
        stream: existing?.stream ?? "",
        timestamp: Date.now(),
      });
      return { thinkingMessages: next };
    }),

  appendThinkingStream: (agent, chunk, fallbackLabel) =>
    set((state) => {
      if (!chunk) return state;
      const next = new Map(state.thinkingMessages);
      const existing = next.get(agent);
      const stream = `${existing?.stream ?? ""}${chunk}`.slice(-STREAM_LIMIT);
      next.set(agent, {
        agent,
        content: existing?.content || fallbackLabel || "Working...",
        stream,
        timestamp: Date.now(),
      });
      return { thinkingMessages: next };
    }),

  setLatestCheckpoint: (checkpoint) => set({ latestCheckpoint: checkpoint }),

  clearThinking: (agent) =>
    set((state) => {
      const next = new Map(state.thinkingMessages);
      next.delete(agent);
      return { thinkingMessages: next };
    }),

  addPhaseResult: (result) =>
    set((state) => {
      const phaseResult: PhaseResult = {
        ...result,
        id: crypto.randomUUID(),
        timestamp: Date.now(),
      };
      return {
        phaseResults: [...state.phaseResults, phaseResult].slice(-20),
        messages: [
          ...state.messages,
          {
            id: crypto.randomUUID(),
            timestamp: Date.now(),
            role: "agent",
            agent: result.agent,
            content: result.summary,
            kind: "phase_result",
            phase: result.phase,
            phaseResult,
          },
        ],
      };
    }),

  setTokenUsage: (usage) => set({ tokenUsage: usage }),

  setTokenBudget: (budget) => set({ tokenBudget: budget }),

  setPhasePercent: (percent) => set({
    phasePercent: percent === null ? null : Math.max(0, Math.min(100, percent)),
  }),

  setLastCompletion: (completion) => set({ lastCompletion: completion }),

  setLastEditDiff: (diff) => set({ lastEditDiff: diff }),

  addActivity: (activity) =>
    set((state) => ({
      activities: [
        ...state.activities,
        { ...activity, id: crypto.randomUUID(), timestamp: Date.now() },
      ].slice(-100),
    })),

  completeActiveActivities: (kind) =>
    set((state) => ({
      activities: state.activities.map((activity) =>
        activity.status === "active" && (!kind || activity.kind === kind)
          ? { ...activity, status: "complete" as const }
          : activity
      ),
    })),

  finishActiveActivities: (kind, status, patch) =>
    set((state) => ({
      activities: state.activities.map((activity) =>
        activity.status === "active" && (!kind || activity.kind === kind)
          ? {
              ...activity,
              status,
              summary: patch?.summary ?? activity.summary,
              details: patch?.details ?? activity.details,
              title: patch?.title ?? activity.title,
              durationMs: patch?.durationMs ?? activity.durationMs,
            }
          : activity
      ),
    })),

  resetAgents: () => set({ agents: [...initialAgents] }),

  reset: () =>
    set({
      messages: [],
      agents: [...initialAgents],
      files: [],
      projectStatus: "created",
      projectStack: "static",
      currentPhase: "",
      pendingFeedback: null,
      buildMode: "team",
      thinkingMessages: new Map(),
      phaseResults: [],
      tokenUsage: null,
      tokenBudget: null,
      phasePercent: null,
      activities: [],
      lastCompletion: null,
      lastEditDiff: null,
      latestCheckpoint: null,
    }),
}));
