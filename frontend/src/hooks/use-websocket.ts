"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { api, getWsUrl } from "@/lib/api";
import { humanizeHeadline, humanizeText, looksLikeJsonBlob } from "@/lib/humanize";
import { getBuildConnectorPayload } from "@/lib/local-settings";
import { useProjectStore } from "@/stores/project-store";
import { useAuthStore } from "@/stores/auth-store";
import type { WSEvent, AgentName, ProjectStatus } from "@/types";

const MAX_RECONNECT_ATTEMPTS = 5;
const BASE_RECONNECT_DELAY_MS = 1_000;
const MAX_RECONNECT_DELAY_MS = 10_000;

const phaseTitles: Record<string, string> = {
  leading: "Understanding the request",
  analyzing: "Researching the problem space",
  planning: "Planning the implementation",
  architecting: "Designing the solution",
  building: "Building and validating files",
};

const TOOL_LABELS: Record<string, string> = {
  write_code_file: "Writing a project file",
  read_project_file: "Reading a project file",
  read_file: "Reading a project file",
  generate_component: "Generating a component",
  read_connector_context: "Reading connector context",
  list_code_files: "Listing project files",
  list_project_files: "Listing project files",
};

function readableToolName(toolName?: string): string {
  if (!toolName) return "Using a project tool";
  const key = toolName.trim().toLowerCase();
  if (TOOL_LABELS[key]) return TOOL_LABELS[key];
  return toolName
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export async function refreshProjectFiles(projectId: string | null): Promise<void> {
  if (!projectId) return;
  try {
    const files = await api.getProjectFiles(projectId);
    useProjectStore.getState().setFiles(files);
  } catch {
    // Ignore stale preview refresh failures.
  }
}

export function useProjectWebSocket(projectId: string | null) {
  const user = useAuthStore((s) => s.user);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const [connected, setConnected] = useState(false);

  const handleEvent = useCallback((event: WSEvent) => {
    const store = useProjectStore.getState();
    switch (event.type) {
      case "phase_start":
        store.completeActiveActivities("phase");
        store.setPhase(event.phase ?? "");
        store.setPhasePercent(event.percent ?? null);
        if (event.usage) store.setTokenUsage(event.usage);
        if (event.token_budget !== undefined) store.setTokenBudget(event.token_budget);
        if (event.phase) {
          store.addActivity({
            kind: "phase",
            phase: event.phase,
            title: phaseTitles[event.phase] ?? `Running ${event.phase}`,
            summary: event.message,
            status: "active",
          });
          const statusMap: Partial<Record<string, ProjectStatus>> = {
            leading: "leading",
            analyzing: "analyzing",
            planning: "planning",
            architecting: "architecting",
            building: "building",
          };
          const s = statusMap[event.phase];
          if (s) {
            store.setProjectStatus(s);
          }
          if (s === "leading" || (s === "building" && !!store.files.length)) {
             store.resetAgents();
          }
        }
        break;

      case "agent_start":
        if (event.agent) {
          store.completeActiveActivities("agent");
          store.updateAgent(event.agent as AgentName, "working", event.task);
          store.addActivity({
            kind: "agent",
            agent: event.agent as AgentName,
            title: event.task ?? "Working on the current phase",
            phase: event.phase,
            status: "active",
          });
        }
        break;

      case "agent_routed":
        if (event.agent) {
          store.setProjectStatus("building");
          store.updateAgent(event.agent as AgentName, "working", "Applying a focused post-build edit");
          store.addMessage({
            role: "system",
            content: event.message ?? "Focused agent edit started.",
          });
          store.addActivity({
            kind: "agent",
            agent: event.agent as AgentName,
            title: "Focused edit routed directly to agent",
            summary: event.message,
            status: "active",
          });
        }
        break;

      case "agent_thinking":
        if (event.agent) {
          store.updateAgent(event.agent as AgentName, "thinking");
          const task = store.agents.find((agent) => agent.agent === event.agent)?.currentTask;
          store.setThinking(event.agent as AgentName, task ?? "Preparing the next step");
        }
        break;

      case "stream_chunk":
        if (event.agent) {
          const agentName = event.agent as AgentName;
          const agentState = store.agents.find((agent) => agent.agent === agentName);
          if (agentState?.status !== "thinking") {
            store.updateAgent(agentName, "thinking");
          }
          const task = agentState?.currentTask ?? "Preparing the next step";
          // Structured phases often stream raw JSON tokens. Keep the status label,
          // but never append JSON fragments into the live thinking panel.
          if (event.content && !looksLikeJsonBlob(event.content) && !looksLikeJsonBlob(store.thinkingMessages.get(agentName)?.stream)) {
            store.appendThinkingStream(agentName, event.content, task);
          } else if (!store.thinkingMessages.has(agentName)) {
            store.setThinking(agentName, task);
          }
          if (store.activities.some((activity) => activity.kind === "tool" && activity.status === "active")) {
            store.completeActiveActivities("tool");
          }
        }
        break;

      case "tool_call":
        if (event.agent) {
          store.completeActiveActivities("tool");
          store.updateAgent(event.agent as AgentName, "working", event.tool_name);
          store.addActivity({
            kind: "tool",
            agent: event.agent as AgentName,
            title: readableToolName(event.tool_name),
            summary: event.content,
            details: event.arguments,
            phase: event.phase,
            status: "active",
          });
        }
        break;

      case "tool_result":
        if (event.agent) {
          const toolStatus = event.status === "error" ? "error" : "complete";
          const durationMs =
            typeof event.duration_ms === "number" && Number.isFinite(event.duration_ms)
              ? Math.max(0, Math.round(event.duration_ms))
              : undefined;
          const hadActiveTool = store.activities.some(
            (activity) => activity.kind === "tool" && activity.status === "active",
          );
          store.finishActiveActivities("tool", toolStatus, {
            summary: event.content ?? (toolStatus === "error" ? "Tool failed" : "Tool finished"),
            details: event.arguments,
            title: readableToolName(event.tool_name),
            durationMs,
          });
          // If no active tool row existed, still record the outcome.
          if (!hadActiveTool) {
            store.addActivity({
              kind: "tool",
              agent: event.agent as AgentName,
              title: readableToolName(event.tool_name),
              summary: event.content,
              details: event.arguments,
              phase: event.phase,
              status: toolStatus,
              durationMs,
            });
          }
          // Keep agent working even on tool errors — the agent may retry.
          store.updateAgent(event.agent as AgentName, "working", event.tool_name);
        }
        break;

      case "agent_step":
        if (event.agent) {
          store.completeActiveActivities("step");
          const stepStatus =
            event.status === "error"
              ? "error"
              : event.status === "complete"
                ? "complete"
                : "active";
          const stepTitle = event.title ?? event.content ?? "Working";
          // Keep agent task labels short — never dump full task prompts into status.
          const shortTask =
            stepTitle.length > 72 || looksLikeJsonBlob(stepTitle)
              ? (event.content && event.content.length <= 72 ? event.content : "Working")
              : stepTitle;
          store.updateAgent(event.agent as AgentName, "working", shortTask);
          store.addActivity({
            kind: "step",
            agent: event.agent as AgentName,
            title: shortTask,
            summary:
              event.content && event.content !== shortTask && !looksLikeJsonBlob(event.content)
                ? event.content
                : undefined,
            phase: event.phase,
            status: stepStatus,
          });
          // Only set thinking for short human labels (e.g. "Composing structured output").
          if (
            stepStatus === "active"
            && shortTask.length <= 72
            && !looksLikeJsonBlob(shortTask)
          ) {
            store.setThinking(event.agent as AgentName, shortTask);
          }
        }
        break;

      case "checkpoint_saved":
        if (event.checkpoint) {
          store.setLatestCheckpoint(event.checkpoint);
        }
        if (event.message) {
          store.addActivity({
            kind: "checkpoint",
            title: "Checkpoint saved",
            summary: event.message,
            status: "complete",
          });
        }
        break;
      case "checkpoint_resume":
        if (event.checkpoint) {
          store.setLatestCheckpoint(event.checkpoint);
        }
        if (event.message) {
          store.addActivity({
            kind: "checkpoint",
            title: "Resumed from checkpoint",
            summary: event.message,
            status: "complete",
          });
        }
        break;

      case "agent_complete":
        if (event.agent) {
          store.completeActiveActivities("tool");
          store.completeActiveActivities("agent");
          store.clearThinking(event.agent as AgentName);
          store.updateAgent(event.agent as AgentName, "complete");
          // Chat cards come from phase_result. agent_complete only updates status.
        }
        break;

      case "phase_result":
        if (event.agent) {
          store.clearThinking(event.agent as AgentName);
          store.updateAgent(event.agent as AgentName, "complete");
          const headline = humanizeHeadline(
            event.headline ?? event.task,
            "Phase complete",
          );
          const summary = humanizeText(
            event.summary ?? event.content,
            headline,
          );
          store.addPhaseResult({
            phase: event.phase ?? store.currentPhase,
            agent: event.agent as AgentName,
            /* v8 ignore next -- kind defaults to markdown when omitted */
            kind: event.kind ?? "markdown",
            headline,
            summary,
            content: summary,
            spec: event.spec ?? null,
            hasStructuredSpec: Boolean(event.has_structured_spec || event.spec),
          });
          store.addActivity({
            kind: "agent",
            agent: event.agent as AgentName,
            phase: event.phase,
            title: headline,
            summary,
            status: "complete",
          });
        }
        break;

      case "file_created":
        if (event.file_path) {
          store.completeActiveActivities("tool");
          store.addFile({
            file_path: event.file_path,
            content: event.content ?? "",
          });
          store.addActivity({
            kind: "file",
            title: `Created ${event.file_path}`,
            details: event.file_path,
            status: "complete",
          });
        }
        break;

      case "token_usage":
      case "usage_update":
        if (event.usage) store.setTokenUsage(event.usage);
        if (event.token_budget !== undefined) store.setTokenBudget(event.token_budget);
        break;

      case "project_complete":
        store.completeActiveActivities();
        store.setPhasePercent(100);
        store.setProjectStatus("complete");
        if (event.usage) {
          store.setTokenUsage(event.usage);
        }
        if (event.token_budget !== undefined) {
          store.setTokenBudget(event.token_budget);
        }
        store.setLastCompletion({
          message: event.message ?? "Project generation complete.",
          mode: event.mode,
          files: Array.isArray(event.files) ? event.files : [],
          filesChanged: Array.isArray(event.files_changed) ? event.files_changed : [],
          checklist: event.checklist ?? null,
          suggestions: Array.isArray(event.suggestions) ? event.suggestions : [],
          timestamp: Date.now(),
          canUndo: Boolean(event.can_undo),
        });
        store.addActivity({
          kind: "phase",
          title:
            event.mode === "iterate"
              ? "Update complete"
              : event.mode === "consult"
                ? "Advice ready"
                : "Build complete",
          summary: event.message ?? "Project generation complete.",
          status: "complete",
        });
        void refreshProjectFiles(projectId);
        break;

      case "edit_diff":
        store.setLastEditDiff({
          filesChanged: Array.isArray(event.files_changed) ? event.files_changed : [],
          diffs: Array.isArray(event.diffs) ? event.diffs : [],
          canUndo: Boolean(event.can_undo),
          message: event.message,
        });
        break;

      case "edit_undone": {
        store.setLastEditDiff(null);
        const prev = store.lastCompletion;
        if (prev) {
          store.setLastCompletion({ ...prev, canUndo: false, filesChanged: [] });
        }
        store.addMessage({
          role: "system",
          content: event.message ?? "Last edit undone.",
        });
        store.addActivity({
          kind: "checkpoint",
          title: "Edit undone",
          summary: event.message ?? "Restored previous files.",
          status: "complete",
        });
        void refreshProjectFiles(projectId);
        break;
      }

      case "human_feedback_request":
        store.completeActiveActivities();
        store.setProjectStatus("awaiting_feedback");
        store.setPendingFeedback({
          phase: event.phase ?? "",
          agent: (event.agent ?? "team_leader") as AgentName,
          content: event.summary ?? event.content ?? "",
          message: event.message ?? "Review output before proceeding",
          summary: event.summary ?? event.content,
          headline: event.headline,
          kind: event.kind,
          spec: event.spec ?? null,
        });
        store.addMessage({
          role: "system",
          content: event.message ?? "Review the output above and approve or request revisions.",
        });
        break;

      case "human_feedback_response":
        store.setPendingFeedback(null);
        store.addMessage({
          role: "system",
          content: event.action === "approve"
            ? "Approved — continuing to next phase..."
            : `Revision requested — regenerating this phase: ${event.feedback ?? ""}`,
        });
        break;

      case "feedback_error":
        store.addMessage({
          role: "system",
          kind: "error",
          category: event.category,
          nextAction: event.next_action,
          content: event.message ?? "Invalid feedback.",
        });
        break;

      case "error":
        store.completeActiveActivities();
        store.setProjectStatus("error");
        if (event.checkpoint) {
          store.setLatestCheckpoint(event.checkpoint);
        }
        if (event.agent) {
          store.clearThinking(event.agent as AgentName);
          store.updateAgent(event.agent as AgentName, "error", event.phase ? `Failed during ${event.phase}` : undefined);
        }
        store.addMessage({
          role: "system",
          kind: "error",
          agent: event.agent as AgentName | undefined,
          phase: event.phase,
          category: event.category,
          details: event.details,
          nextAction: event.next_action,
          content: event.message ?? "Unknown error",
        });
        break;
    }
  }, [projectId]);

  useEffect(() => {
    if (!projectId || !user) return;

    let cancelled = false;
    reconnectAttemptsRef.current = 0;

    const clearReconnectTimer = () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };

    const connect = () => {
      clearReconnectTimer();

      const ws = new WebSocket(getWsUrl(projectId));
      wsRef.current = ws;

      ws.onopen = () => {
        if (cancelled || wsRef.current !== ws) return;
        reconnectAttemptsRef.current = 0;
        setConnected(true);
      };

      ws.onmessage = (e) => {
        if (cancelled || wsRef.current !== ws) return;
        try {
          const event: WSEvent = JSON.parse(e.data);
          handleEvent(event);
        } catch {
          useProjectStore.getState().addMessage({
            role: "system",
            content: "Received an invalid server message.",
          });
        }
      };

      ws.onerror = () => {
        if (cancelled || wsRef.current !== ws) return;
        setConnected(false);
      };

      ws.onclose = () => {
        const wasActive = wsRef.current === ws;
        if (!wasActive) return;
        wsRef.current = null;
        setConnected(false);

        reconnectAttemptsRef.current += 1;
        if (reconnectAttemptsRef.current > MAX_RECONNECT_ATTEMPTS) {
          useProjectStore.getState().addMessage({
            role: "system",
            content: "Connection lost. Refresh the page to reconnect.",
          });
          return;
        }

        const delay = Math.min(
          BASE_RECONNECT_DELAY_MS * 2 ** (reconnectAttemptsRef.current - 1),
          MAX_RECONNECT_DELAY_MS
        );
        reconnectTimerRef.current = setTimeout(connect, delay);
      };
    };

    connect();

    return () => {
      cancelled = true;
      clearReconnectTimer();
      const activeSocket = wsRef.current;
      wsRef.current = null;
      activeSocket?.close();
      setConnected(false);
    };
  }, [projectId, handleEvent, user]);

  const send = useCallback((data: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  const startBuild = useCallback(
    (prompt: string) => {
      const mode = useProjectStore.getState().buildMode;
      const connectors = getBuildConnectorPayload();
      useProjectStore.setState({
        activities: [],
        thinkingMessages: new Map(),
        tokenUsage: null,
        tokenBudget: null,
        phasePercent: null,
      });
      useProjectStore.getState().addMessage({ role: "user", content: prompt });
      send({ type: "start_build", prompt, mode, connectors });
    },
    [send]
  );

  const resumeBuild = useCallback(
    (prompt: string, checkpoint?: string | null) => {
      const mode = useProjectStore.getState().buildMode;
      const connectors = getBuildConnectorPayload();
      const resolvedCheckpoint = checkpoint ?? useProjectStore.getState().latestCheckpoint;
      send({
        type: "resume_build",
        prompt,
        mode,
        connectors,
        checkpoint: resolvedCheckpoint ?? undefined,
      });
    },
    [send]
  );

  const forkBuild = useCallback(
    (prompt: string, checkpoint?: string | null, branch?: string) => {
      const mode = useProjectStore.getState().buildMode;
      const connectors = getBuildConnectorPayload();
      const resolvedCheckpoint = checkpoint ?? useProjectStore.getState().latestCheckpoint;
      send({
        type: "fork_build",
        prompt,
        mode,
        connectors,
        checkpoint: resolvedCheckpoint ?? undefined,
        branch,
      });
    },
    [send]
  );

  const sendFeedback = useCallback(
    (action: "approve" | "revise", feedback?: string) => {
      send({ type: "human_feedback", action, feedback: feedback ?? "" });
    },
    [send]
  );

  const undoLastEdit = useCallback(() => {
    send({ type: "undo_last_edit" });
  }, [send]);

  return { send, startBuild, resumeBuild, forkBuild, sendFeedback, undoLastEdit, connected };
}
