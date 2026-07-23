"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Bot,
  Check,
  ChevronDown,
  CircleDashed,
  FileCode2,
  ListTree,
  Loader2,
  RotateCcw,
  Timer,
  Wrench,
  X,
} from "lucide-react";
import { humanizeHeadline, humanizeText, looksLikeJsonBlob } from "@/lib/humanize";
import { cn } from "@/lib/utils";
import { useProjectStore } from "@/stores/project-store";
import { AGENTS, type BuildActivity } from "@/types";

const COLLAPSED_ACTIVITY_COUNT = 8;

const activityIcon: Record<BuildActivity["kind"], typeof Bot> = {
  phase: CircleDashed,
  agent: Bot,
  tool: Wrench,
  file: FileCode2,
  checkpoint: RotateCcw,
  step: ListTree,
};

function safeDetails(value: string): string {
  return value
    .replace(
      /("?(?:api[_-]?key|access[_-]?token|refresh[_-]?token|authorization|password|secret)"?\s*[:=]\s*)"?[^",\s}]+"?/gi,
      "$1[redacted]",
    )
    .replace(/Bearer\s+[A-Za-z0-9._~+\/-]+/gi, "Bearer [redacted]");
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 10_000) return `${(ms / 1000).toFixed(1)}s`;
  if (ms < 60_000) return `${Math.round(ms / 1000)}s`;
  const minutes = Math.floor(ms / 60_000);
  const seconds = Math.round((ms % 60_000) / 1000);
  return seconds > 0 ? `${minutes}m ${seconds}s` : `${minutes}m`;
}

function formatRelativeTime(timestamp: number, now: number): string {
  const delta = Math.max(0, now - timestamp);
  if (delta < 5_000) return "just now";
  if (delta < 60_000) return `${Math.round(delta / 1000)}s ago`;
  if (delta < 3_600_000) return `${Math.round(delta / 60_000)}m ago`;
  return `${Math.round(delta / 3_600_000)}h ago`;
}

/** Compact stats line: "2 tools · 13 steps · 2 files" */
export function summarizeActivities(activities: BuildActivity[]): string {
  const tools = activities.filter((a) => a.kind === "tool");
  const toolsDone = tools.filter((a) => a.status === "complete").length;
  const toolsError = tools.filter((a) => a.status === "error").length;
  const steps = activities.filter((a) => a.kind === "step").length;
  const files = activities.filter((a) => a.kind === "file").length;
  const parts: string[] = [];
  if (toolsDone + toolsError > 0) {
    parts.push(
      toolsError > 0
        ? `${toolsDone + toolsError} tools (${toolsError} failed)`
        : `${toolsDone} tool${toolsDone === 1 ? "" : "s"}`,
    );
  }
  if (steps > 0) {
    parts.push(steps === 1 ? "1 step" : `${steps} steps`);
  }
  if (files > 0) {
    parts.push(files === 1 ? "1 file" : `${files} files`);
  }
  return parts.join(" · ");
}

/** Full header subtitle used by Live Session and the standalone activity panel. */
export function activitySessionSummary(
  activities: BuildActivity[],
  options: { live: boolean },
): string {
  const stats = summarizeActivities(activities);
  const lead = options.live
    ? "Live execution updates"
    : `${activities.length} recorded update${activities.length === 1 ? "" : "s"}`;
  return stats ? `${lead} · ${stats}` : lead;
}

function useNow(enabled: boolean, intervalMs = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!enabled) return;
    const id = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(id);
  }, [enabled, intervalMs]);
  return now;
}

function StatusGlyph({
  activity,
  Icon,
}: {
  activity: BuildActivity;
  Icon: typeof Bot;
}) {
  if (activity.status === "complete") {
    return (
      <span className="flex h-6 w-6 items-center justify-center rounded-full border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
        <Check className="h-3 w-3" aria-hidden="true" />
      </span>
    );
  }
  if (activity.status === "error") {
    return (
      <span className="flex h-6 w-6 items-center justify-center rounded-full border border-red-500/40 bg-red-500/10 text-red-400">
        <X className="h-3 w-3" aria-hidden="true" />
      </span>
    );
  }
  // Active work — spinner for tools, pulse icon for steps/phases.
  return (
    <span className="relative flex h-6 w-6 items-center justify-center rounded-full border border-accent/50 bg-background text-accent animate-timeline-glow">
      {activity.kind === "tool" ? (
        <Loader2 className="h-3 w-3 animate-spin-slow" aria-hidden="true" />
      ) : (
        <Icon className="h-3 w-3 animate-pulse" aria-hidden="true" />
      )}
    </span>
  );
}

function ActivityRow({
  activity,
  isLast,
  verbose,
  now,
}: {
  activity: BuildActivity;
  isLast: boolean;
  verbose: boolean;
  now: number;
}) {
  const Icon = activityIcon[activity.kind];
  const agent = activity.agent
    ? AGENTS.find((item) => item.id === activity.agent) ?? null
    : null;
  const active = activity.status === "active";
  const errored = activity.status === "error";
  const [open, setOpen] = useState(false);
  const showDetails = Boolean(activity.details) && (verbose || activity.kind === "tool" || activity.kind === "file");
  const liveMs =
    active && activity.kind === "tool"
      ? Math.max(0, now - activity.timestamp)
      : null;
  const durationLabel =
    typeof activity.durationMs === "number"
      ? formatDuration(activity.durationMs)
      : liveMs !== null
        ? formatDuration(liveMs)
        : null;

  const title = humanizeHeadline(
    activity.title,
    activity.kind === "agent" ? "Agent update" : "Update",
  );

  return (
    <li className="relative flex gap-3 pb-3.5 last:pb-0">
      {!isLast ? (
        <span
          className={cn(
            "absolute left-[11px] top-7 h-[calc(100%-14px)] w-px",
            active ? "bg-accent/30" : "bg-border/80",
          )}
        />
      ) : null}
      <div className="relative z-10 mt-0.5 shrink-0">
        <StatusGlyph activity={activity} Icon={Icon} />
      </div>
      <div
        className={cn(
          "min-w-0 flex-1 rounded-xl border px-2.5 py-2 transition-colors",
          active && "border-accent/25 bg-accent/[0.04]",
          errored && "border-red-500/25 bg-red-500/[0.04]",
          !active && !errored && "border-transparent bg-transparent hover:bg-surface/40",
        )}
      >
        <div className="flex min-w-0 items-center gap-2">
          <p
            className={cn(
              "min-w-0 flex-1 truncate text-[12px] font-medium leading-tight",
              "text-foreground",
            )}
          >
            {title}
          </p>
          {agent ? (
            <span
              className="shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium"
              style={{
                color: agent.color,
                backgroundColor: `color-mix(in srgb, ${agent.color} 12%, transparent)`,
              }}
            >
              {agent.name}
            </span>
          ) : null}
          {durationLabel ? (
            <span className="inline-flex shrink-0 items-center gap-0.5 text-[10px] tabular-nums text-muted">
              <Timer className="h-2.5 w-2.5" aria-hidden="true" />
              {durationLabel}
            </span>
          ) : null}
          {verbose ? (
            <span className="shrink-0 text-[10px] tabular-nums text-muted/80">
              {formatRelativeTime(activity.timestamp, now)}
            </span>
          ) : null}
          {active ? <span className="sr-only">In progress</span> : null}
          {errored ? <span className="sr-only">Failed</span> : null}
        </div>

        {activity.summary && !looksLikeJsonBlob(activity.summary) ? (
          <p className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-muted">
            {humanizeText(activity.summary)}
          </p>
        ) : null}

        {showDetails && activity.details ? (
          <div className="mt-1.5">
            {verbose && activity.kind === "tool" ? (
              <pre className="max-h-36 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-border/70 bg-background/70 p-2 font-mono text-[10px] leading-relaxed text-muted">
                {safeDetails(activity.details)}
              </pre>
            ) : (
              <>
                <button
                  type="button"
                  onClick={() => setOpen((value) => !value)}
                  className="inline-flex items-center gap-1 text-[11px] font-medium text-accent transition-colors hover:text-accent-hover"
                  aria-expanded={open}
                >
                  {open ? "Hide details" : "View output"}
                  <ChevronDown
                    className={cn("h-3 w-3 transition-transform", open && "rotate-180")}
                    aria-hidden="true"
                  />
                </button>
                {open ? (
                  <pre className="mt-1.5 max-h-36 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-border/70 bg-background/70 p-2 font-mono text-[10px] leading-relaxed text-muted">
                    {safeDetails(activity.details)}
                  </pre>
                ) : null}
              </>
            )}
          </div>
        ) : null}
      </div>
    </li>
  );
}

export function ActivityPanel({ embedded = false }: { embedded?: boolean }) {
  const activities = useProjectStore((state) => state.activities);
  const [expanded, setExpanded] = useState(false);
  const [verbose, setVerbose] = useState(false);
  const listRef = useRef<HTMLOListElement>(null);
  const hasActiveActivity = activities.some((activity) => activity.status === "active");
  const now = useNow(hasActiveActivity || verbose);

  const sessionSummary = useMemo(
    () => activitySessionSummary(activities, { live: hasActiveActivity }),
    [activities, hasActiveActivity],
  );
  const hiddenCount = Math.max(0, activities.length - COLLAPSED_ACTIVITY_COUNT);
  const visible = expanded ? activities : activities.slice(-COLLAPSED_ACTIVITY_COUNT);

  useEffect(() => {
    if (!listRef.current || expanded) return;
    listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [activities.length, expanded, hasActiveActivity]);

  if (activities.length === 0) return null;

  const body = (
    <>
      <div
        className={cn(
          "flex items-center justify-between gap-3",
          // Embedded under Live Session: summary lives in the shell header.
          embedded ? "pb-1.5" : "border-b border-border px-3 py-2.5",
        )}
      >
        <div className="min-w-0">
          {!embedded ? (
            <>
              <h2 id="build-activity-title" className="text-xs font-semibold text-foreground">
                Build activity
              </h2>
              <p className="text-[10px] text-muted">
                {hasActiveActivity ? (
                  <span className="inline-flex items-center gap-1.5">
                    <span className="relative flex h-1.5 w-1.5">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-50" />
                      <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400" />
                    </span>
                    {sessionSummary}
                  </span>
                ) : (
                  sessionSummary
                )}
              </p>
            </>
          ) : (
            <p id="build-activity-title" className="sr-only">
              Build activity timeline
            </p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            onClick={() => setVerbose((value) => !value)}
            className={cn(
              "inline-flex min-h-7 items-center rounded-md px-2 text-[11px] transition-colors focus:outline-none focus:ring-2 focus:ring-accent/50",
              verbose
                ? "bg-accent/10 text-accent"
                : "text-muted hover:bg-surface hover:text-foreground",
            )}
            aria-pressed={verbose}
            title="Show timestamps and expand tool details"
          >
            Verbose
          </button>
          {hiddenCount > 0 ? (
            <button
              type="button"
              onClick={() => setExpanded((value) => !value)}
              className="inline-flex min-h-7 items-center gap-1 rounded-md px-2 text-[11px] text-muted transition-colors hover:bg-surface hover:text-foreground focus:outline-none focus:ring-2 focus:ring-accent/50"
              aria-expanded={expanded}
            >
              {expanded ? "Show recent" : `${hiddenCount} earlier`}
              <ChevronDown
                className={cn("h-3 w-3 transition-transform", expanded && "rotate-180")}
                aria-hidden="true"
              />
            </button>
          ) : null}
        </div>
      </div>
      <ol
        ref={listRef}
        className={cn(
          "px-1",
          embedded ? "max-h-64 overflow-y-auto pt-1" : "px-3 py-3",
          !embedded && "max-h-80 overflow-y-auto",
        )}
      >
        {visible.map((activity, index) => (
          <ActivityRow
            key={activity.id}
            activity={activity}
            isLast={index === visible.length - 1}
            verbose={verbose}
            now={now}
          />
        ))}
      </ol>
    </>
  );

  if (embedded) {
    return <div aria-labelledby="build-activity-title">{body}</div>;
  }

  return (
    <section
      className="mx-2 my-3 overflow-hidden rounded-2xl border border-border/80 bg-surface/50 shadow-sm"
      aria-labelledby="build-activity-title"
    >
      {body}
    </section>
  );
}
