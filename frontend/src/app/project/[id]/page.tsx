"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { Header } from "@/components/layout/header";
import { AgentStatusBar } from "@/components/workspace/agent-status";
import { ChatPanel } from "@/components/workspace/chat-panel";
import { PreviewPanel } from "@/components/workspace/preview-panel";
import { SplitPane } from "@/components/workspace/split-pane";
import { UsageSummary } from "@/components/workspace/usage-summary";
import { useProjectWebSocket } from "@/hooks/use-websocket";
import { useProjectStore } from "@/stores/project-store";
import { api } from "@/lib/api";
import type { BuildMode, Message, PhaseResultKind, Project, ProjectFile } from "@/types";

const PHASE_RESULT_KINDS = new Set<PhaseResultKind>([
  "brief",
  "analysis",
  "plan",
  "architecture",
  "build",
  "markdown",
]);
import { Skeleton } from "@/components/ui/skeleton";
import { useAuthStore } from "@/stores/auth-store";

interface ProjectMessageResponse {
  id: string | number;
  role: Message["role"];
  agent?: Message["agent"];
  content: string;
  created_at: string;
  kind?: Message["kind"] | null;
  metadata?: {
    phase?: string;
    kind?: string;
    headline?: string;
    summary?: string;
    spec?: Record<string, unknown> | null;
    has_structured_spec?: boolean;
  } | null;
}

function hydrateMessage(message: ProjectMessageResponse): Message {
  const base: Message = {
    id: String(message.id),
    role: message.role,
    agent: message.agent,
    content: message.content,
    timestamp: new Date(message.created_at).getTime(),
  };

  if (message.kind === "phase_result") {
    const meta = message.metadata ?? {};
    const summary = (typeof meta.summary === "string" && meta.summary.trim())
      ? meta.summary
      : message.content;
    const headline = (typeof meta.headline === "string" && meta.headline.trim())
      ? meta.headline
      : summary.slice(0, 80) || "Phase complete";
    const kindValue = String(meta.kind ?? "markdown") as PhaseResultKind;
    const kind: PhaseResultKind = PHASE_RESULT_KINDS.has(kindValue) ? kindValue : "markdown";
    return {
      ...base,
      content: summary,
      kind: "phase_result",
      phase: typeof meta.phase === "string" ? meta.phase : undefined,
      phaseResult: {
        id: `msg-${message.id}`,
        phase: typeof meta.phase === "string" ? meta.phase : "",
        agent: (message.agent ?? "team_leader") as NonNullable<Message["agent"]>,
        kind,
        headline,
        summary,
        content: summary,
        spec: meta.spec ?? null,
        hasStructuredSpec: Boolean(meta.has_structured_spec || meta.spec),
        timestamp: base.timestamp,
      },
    };
  }

  if (message.kind === "thinking" || message.kind === "error") {
    return { ...base, kind: message.kind };
  }

  // Legacy rows: plain agent summaries without phase_result metadata still
  // render as simple bubbles (pre-metadata builds).
  return base;
}

function ProjectWorkspaceContent() {
  const params = useParams();
  const projectId = params.id as string;
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<"not_found" | "unauthorized" | "unavailable" | null>(null);
  const user = useAuthStore((s) => s.user);
  const authLoading = useAuthStore((s) => s.loading);
  const autostartedRef = useRef(false);
  const reset = useProjectStore((s) => s.reset);
  const setMessages = useProjectStore((s) => s.setMessages);
  const setFiles = useProjectStore((s) => s.setFiles);
  const setProjectStatus = useProjectStore((s) => s.setProjectStatus);
  const setProjectStack = useProjectStore((s) => s.setProjectStack);
  const setBuildMode = useProjectStore((s) => s.setBuildMode);
  const projectStatus = useProjectStore((s) => s.projectStatus);
  const { send, startBuild, resumeBuild, sendFeedback, undoLastEdit, connected } = useProjectWebSocket(projectId);
  const setLatestCheckpoint = useProjectStore((s) => s.setLatestCheckpoint);
  const setTokenUsage = useProjectStore((s) => s.setTokenUsage);
  const setTokenBudget = useProjectStore((s) => s.setTokenBudget);
  const handlePreviewMessage = useCallback((msg: string) => {
    const content = msg.trim();
    if (!content) return;
    useProjectStore.getState().addMessage({ role: "user", content });
    // Select-to-edit and console "Fix" prompts are always focused engineer edits.
    const targetAgent = /^@(engineer|ravi)\b/i.test(content) ? "engineer" as const : undefined;
    send({
      type: "message",
      content,
      ...(targetAgent ? { target_agent: targetAgent } : {}),
    });
  }, [send]);

  useEffect(() => {
    if (authLoading || !user) return;
    let cancelled = false;

    void Promise.resolve()
      .then(() => {
        /* v8 ignore next -- promise may settle after route unmount */
        if (cancelled) return null;
        reset();
        setLoadError(null);
        setLoading(true);
        return Promise.all([
          api.getProject(projectId),
          api.getProjectMessages(projectId),
          api.getProjectFiles(projectId),
          api.getProjectCheckpoints(projectId).catch(() => ({ checkpoints: [], latest: null })),
        ]);
      })
      .then((results) => {
        /* v8 ignore next -- stale route result is intentionally discarded */
        if (!results || cancelled) return;
        const [projectResult, messageResults, fileResults, checkpointResult] = results;
        const loadedProject = projectResult as Project;
        const loadedMessages = messageResults as ProjectMessageResponse[];
        const loadedFiles = fileResults as ProjectFile[];

        setProject(loadedProject);
        setProjectStatus(loadedProject.status);
        setProjectStack(loadedProject.stack ?? "static");
        setTokenUsage(loadedProject.token_usage ?? null);
        setTokenBudget(loadedProject.token_budget ?? null);
        setMessages(loadedMessages.map(hydrateMessage));
        setFiles(loadedFiles);
        setLatestCheckpoint(checkpointResult.latest);
      })
      .catch((error: unknown) => {
        /* v8 ignore next -- stale route failures are intentionally discarded */
        if (cancelled) return;
        setProject(null);
        const message = error instanceof Error ? error.message.toLowerCase() : "";
        if (message.includes("authentication")) {
          setLoadError("unauthorized");
        } else if (message.includes("not found")) {
          setLoadError("not_found");
        } else {
          setLoadError("unavailable");
        }
      })
      .finally(() => {
        /* v8 ignore next -- stale route cleanup must not update state */
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, projectId, reset, setFiles, setLatestCheckpoint, setMessages, setProjectStack, setProjectStatus, setTokenBudget, setTokenUsage, user]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("autostart") !== "true" || !connected || !project || projectStatus !== "created") {
      return;
    }

    const autostartKey = `neutron-autostart:${projectId}`;
    if (autostartedRef.current || sessionStorage.getItem(autostartKey) === "1") {
      autostartedRef.current = true;
      return;
    }

    autostartedRef.current = true;
    sessionStorage.setItem(autostartKey, "1");

    const mode = params.get("mode") as BuildMode | null;
    if (mode) setBuildMode(mode);
    startBuild(project.description);

    params.delete("autostart");
    const nextQuery = params.toString();
    const nextUrl = nextQuery ? `${window.location.pathname}?${nextQuery}` : window.location.pathname;
    window.history.replaceState({}, "", nextUrl);
  }, [connected, project, projectId, projectStatus, startBuild, setBuildMode]);

  if (!user && !authLoading) {
    return (
      <div className="flex h-[100dvh] flex-col">
        <Header />
        <div className="flex-1 flex items-center justify-center px-6 text-center">
          <div>
            <h1 className="text-2xl font-semibold text-foreground mb-2">Log in to open this workspace.</h1>
            <p className="text-sm text-muted mb-5">Builds require an account so projects and provider keys stay private.</p>
            <a href="/login" className="inline-flex items-center justify-center rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white shadow-lg shadow-accent/25 transition-all duration-200 hover:bg-accent-hover focus:outline-none focus:ring-2 focus:ring-accent/50">Log in</a>
          </div>
        </div>
      </div>
    );
  }

  if (loading || authLoading) {
    return (
      <div className="flex h-[100dvh] flex-col">
        <Header />
        <div className="flex-1 flex items-center justify-center">
          <Skeleton className="w-96 h-8" />
        </div>
      </div>
    );
  }

  if (!project) {
    const copy = loadError === "unauthorized"
      ? { title: "Session expired", body: "Log in again to open this workspace.", action: "Log in", href: "/login" }
      : loadError === "unavailable"
        ? { title: "Could not load project", body: "The server may be unavailable. Refresh and try again.", action: "Refresh", href: undefined }
        : { title: "Project not found", body: "This project may have been deleted or you may not have access.", action: "Back to dashboard", href: "/dashboard" };
    return (
      <div className="flex h-[100dvh] flex-col">
        <Header />
        <div className="flex-1 flex items-center justify-center px-6 text-center">
          <div>
            <h1 className="text-2xl font-semibold text-foreground mb-2">{copy.title}</h1>
            <p className="text-sm text-muted mb-5">{copy.body}</p>
            {copy.href ? (
              <a href={copy.href} className="inline-flex items-center justify-center rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white shadow-lg shadow-accent/25 transition-all duration-200 hover:bg-accent-hover focus:outline-none focus:ring-2 focus:ring-accent/50">{copy.action}</a>
            ) : (
              <button type="button" onClick={() => window.location.reload()} className="inline-flex items-center justify-center rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white shadow-lg shadow-accent/25 transition-all duration-200 hover:bg-accent-hover focus:outline-none focus:ring-2 focus:ring-accent/50">{copy.action}</button>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-[100dvh] flex-col">
      <Header />
      <AgentStatusBar connected={connected} projectId={projectId} />
      <UsageSummary />
      <div className="flex-1 overflow-hidden">
        <SplitPane
          left={
            <ChatPanel
              projectId={projectId}
              onSend={(msg, targetAgent) => {
                useProjectStore.getState().addMessage({ role: "user", content: msg });
                send({ type: "message", content: msg, ...(targetAgent ? { target_agent: targetAgent } : {}) });
              }}
              onStartBuild={startBuild}
              onResumeBuild={resumeBuild}
              onFeedback={sendFeedback}
              onUndo={undoLastEdit}
              projectDescription={project.description}
            />
          }
          right={
            <PreviewPanel projectId={projectId} onSendMessage={handlePreviewMessage} />
          }
        />
      </div>
    </div>
  );
}

export default function ProjectWorkspace() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[100dvh] flex-col">
          <Header />
          <div className="flex-1 flex items-center justify-center">
            <Skeleton className="w-96 h-8" />
          </div>
        </div>
      }
    >
      <ProjectWorkspaceContent />
    </Suspense>
  );
}
