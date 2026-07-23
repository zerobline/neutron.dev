"use client";

import { useMemo } from "react";
import { Activity, Radio } from "lucide-react";
import { cn } from "@/lib/utils";
import { useProjectStore } from "@/stores/project-store";
import { AGENTS, type AgentName } from "@/types";
import { ActivityPanel, activitySessionSummary } from "./activity-panel";
import { ThinkingIndicator } from "./thinking-indicator";

const phaseLabels: Record<string, string> = {
  leading: "Understanding",
  analyzing: "Research",
  planning: "Planning",
  architecting: "Architecture",
  building: "Building",
  awaiting_feedback: "Awaiting review",
};

const LIVE_STATUSES = new Set([
  "leading",
  "analyzing",
  "planning",
  "architecting",
  "building",
]);

function resolveAgent(id: AgentName | undefined) {
  if (!id) return null;
  return AGENTS.find((agent) => agent.id === id) ?? null;
}

/**
 * Manus-style unified live work surface: current agent stream + session timeline.
 * Renders only while a build has thinking and/or activity events.
 */
export function LiveSession() {
  const activities = useProjectStore((s) => s.activities);
  const thinkingMessages = useProjectStore((s) => s.thinkingMessages);
  const currentPhase = useProjectStore((s) => s.currentPhase);
  const phasePercent = useProjectStore((s) => s.phasePercent);
  const agents = useProjectStore((s) => s.agents);
  const projectStatus = useProjectStore((s) => s.projectStatus);

  const hasThinking = thinkingMessages.size > 0;
  const hasActivities = activities.length > 0;
  const isComplete = projectStatus === "complete";
  const isFailed = projectStatus === "error";
  const isLive =
    !isComplete &&
    !isFailed &&
    (hasThinking ||
      activities.some((a) => a.status === "active") ||
      LIVE_STATUSES.has(projectStatus));

  const activeAgent = useMemo(() => {
    if (isComplete || isFailed) return null;
    const thinkingId = Array.from(thinkingMessages.keys())[0];
    if (thinkingId) return resolveAgent(thinkingId);

    const working = agents.find((a) => a.status === "working" || a.status === "thinking");
    if (working) return resolveAgent(working.agent);

    const lastWithAgent = [...activities].reverse().find((a) => a.agent);
    return resolveAgent(lastWithAgent?.agent);
  }, [thinkingMessages, agents, activities, isComplete, isFailed]);

  // Prefer the classic stats line at the top of the shell:
  // "Live execution updates · 2 tools · 13 steps · 2 files"
  // Must run before any early return — React hooks cannot be conditional (error #310).
  const sessionSummary = useMemo(() => {
    if (hasActivities) {
      return activitySessionSummary(activities, { live: isLive });
    }
    if (isComplete) return "Build finished — review the phase cards below";
    if (isFailed) return "Build stopped";
    return "Agent execution timeline";
  }, [activities, hasActivities, isComplete, isFailed, isLive]);

  if (!hasThinking && !hasActivities) return null;

  // After the build finishes, never keep showing "Building · 100%".
  const phaseLabel = isComplete
    ? "Complete"
    : isFailed
      ? "Failed"
      : currentPhase
        ? (phaseLabels[currentPhase] ?? `${currentPhase.charAt(0).toUpperCase()}${currentPhase.slice(1)}`)
        : null;

  const showProgress = typeof phasePercent === "number" && isLive;
  const phaseBadgeText =
    phaseLabel && isLive && typeof phasePercent === "number"
      ? `${phaseLabel} · ${phasePercent}%`
      : phaseLabel;

  return (
    <section
      className="mx-1 my-2 overflow-hidden rounded-2xl border border-border/80 bg-surface/60 shadow-[0_8px_30px_rgba(0,0,0,0.12)] animate-slide-up"
      aria-label="Live agent session"
    >
      <header className="flex items-center justify-between gap-3 border-b border-border/70 bg-background/30 px-3.5 py-2.5">
        <div className="flex min-w-0 items-center gap-2.5">
          <span
            className={cn(
              "flex h-7 w-7 items-center justify-center rounded-lg border",
              isLive
                ? "border-accent/30 bg-accent/10 text-accent"
                : "border-border bg-surface text-muted",
            )}
          >
            {isLive ? (
              <Radio className="h-3.5 w-3.5" aria-hidden="true" />
            ) : (
              <Activity className="h-3.5 w-3.5" aria-hidden="true" />
            )}
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-xs font-semibold tracking-tight text-foreground">
                {isLive ? "Live session" : "Session log"}
              </h2>
              {isLive ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-medium text-emerald-400">
                  <span className="h-1 w-1 rounded-full bg-emerald-400 animate-pulse-dot" />
                  Live
                </span>
              ) : null}
              {phaseBadgeText ? (
                <span
                  className={cn(
                    "rounded-full border px-1.5 py-0.5 text-[10px]",
                    isComplete
                      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                      : isFailed
                        ? "border-red-500/30 bg-red-500/10 text-red-400"
                        : "border-border/80 bg-background/50 text-muted",
                  )}
                >
                  {phaseBadgeText}
                </span>
              ) : null}
            </div>
            <p className="mt-0.5 truncate text-[11px] text-muted">
              {isLive && hasActivities ? (
                <span className="inline-flex max-w-full items-center gap-1.5">
                  <span className="relative flex h-1.5 w-1.5 shrink-0">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-50" />
                    <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400" />
                  </span>
                  <span className="truncate">{sessionSummary}</span>
                </span>
              ) : (
                sessionSummary
              )}
            </p>
            {activeAgent ? (
              <p className="mt-0.5 truncate text-[10px] text-muted/80">
                <span style={{ color: activeAgent.color }} className="font-medium">
                  {activeAgent.name}
                </span>
                <span> · {activeAgent.role}</span>
              </p>
            ) : null}
          </div>
        </div>
        {showProgress ? (
          <div className="hidden w-24 shrink-0 sm:block" aria-hidden="true">
            <div className="h-1 overflow-hidden rounded-full bg-border/80">
              <div
                className="h-full rounded-full bg-accent transition-[width] duration-500 ease-out"
                style={{ width: `${Math.min(100, Math.max(0, phasePercent))}%` }}
              />
            </div>
          </div>
        ) : null}
      </header>

      <div className="space-y-3 px-3 py-3">
        {hasThinking ? <ThinkingIndicator embedded /> : null}
        {hasActivities ? (
          <div className={cn(hasThinking && "border-t border-border/50 pt-3")}>
            <ActivityPanel embedded />
          </div>
        ) : null}
      </div>
    </section>
  );
}
