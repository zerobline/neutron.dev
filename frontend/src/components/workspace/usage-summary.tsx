"use client";

import { Gauge, Zap } from "lucide-react";
import { useProjectStore } from "@/stores/project-store";

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

const phaseProgress: Record<string, number> = {
  leading: 8,
  analyzing: 25,
  planning: 45,
  architecting: 65,
  building: 82,
};

export function UsageSummary() {
  const tokenUsage = useProjectStore((s) => s.tokenUsage);
  const tokenBudget = useProjectStore((s) => s.tokenBudget);
  const currentPhase = useProjectStore((s) => s.currentPhase);
  const phasePercent = useProjectStore((s) => s.phasePercent);
  const projectStatus = useProjectStore((s) => s.projectStatus);

  if (projectStatus === "created" && !tokenUsage && !tokenBudget) return null;

  const usedTokens = tokenUsage?.total_tokens ?? 0;
  const budgetPercent = tokenBudget && tokenBudget > 0
    ? Math.min(100, Math.round((usedTokens / tokenBudget) * 100))
    : null;
  const isComplete = projectStatus === "complete";
  const isFailed = projectStatus === "error";
  const phaseLabel = isComplete
    ? "Complete"
    : isFailed
      ? "Failed"
      : currentPhase
        ? currentPhase.charAt(0).toUpperCase() + currentPhase.slice(1)
        : "Preparing";
  // When finished, drop the percent and progress bar so refresh doesn't look mid-build.
  const progress = isComplete || isFailed
    ? null
    : phasePercent ?? phaseProgress[currentPhase] ?? null;

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-border bg-background/70 px-4 py-2 text-[11px] text-muted">
      <div className="flex min-w-[130px] items-center gap-2">
        <Gauge
          className={
            isComplete
              ? "h-3.5 w-3.5 text-emerald-400"
              : isFailed
                ? "h-3.5 w-3.5 text-red-400"
                : "h-3.5 w-3.5 text-accent"
          }
          aria-hidden="true"
        />
        <span>
          <span
            className={
              isComplete
                ? "text-emerald-400"
                : isFailed
                  ? "text-red-400"
                  : "text-foreground"
            }
          >
            {phaseLabel}
          </span>
          {progress !== null ? ` · ${progress}%` : ""}
        </span>
      </div>
      {progress !== null ? (
        <div
          className="h-1.5 min-w-24 flex-1 overflow-hidden rounded-full bg-border/70"
          role="progressbar"
          aria-label="Build progress"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={progress}
        >
          <div className="h-full rounded-full bg-accent transition-[width] duration-300" style={{ width: `${progress}%` }} />
        </div>
      ) : null}
      <div className="flex items-center gap-2 whitespace-nowrap">
        <Zap className="h-3.5 w-3.5 text-amber-400" aria-hidden="true" />
        <span className="text-foreground">{formatTokens(usedTokens)} tokens</span>
        {tokenBudget ? <span>of {formatTokens(tokenBudget)} · {budgetPercent}%</span> : null}
        {tokenUsage ? (
          <span className="hidden items-center gap-1 md:inline-flex">
            <span>{formatTokens(tokenUsage.prompt_tokens)} in</span>
            <span aria-hidden="true">·</span>
            <span>{formatTokens(tokenUsage.completion_tokens)} out</span>
            <span aria-hidden="true">·</span>
            <span>{tokenUsage.successful_requests} requests</span>
          </span>
        ) : null}
      </div>
    </div>
  );
}
