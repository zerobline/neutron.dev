"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, FileDiff, RotateCcw } from "lucide-react";
import { useProjectStore } from "@/stores/project-store";
import { cn } from "@/lib/utils";

interface EditDiffPanelProps {
  onUndo?: () => void;
}

export function EditDiffPanel({ onUndo }: EditDiffPanelProps) {
  const lastEditDiff = useProjectStore((s) => s.lastEditDiff);
  const projectStatus = useProjectStore((s) => s.projectStatus);
  const [expandedPath, setExpandedPath] = useState<string | null>(null);
  const [undoing, setUndoing] = useState(false);

  if (!lastEditDiff || lastEditDiff.filesChanged.length === 0) return null;
  if (projectStatus === "building") return null;

  const handleUndo = () => {
    if (!onUndo || !lastEditDiff.canUndo) return;
    setUndoing(true);
    onUndo();
    window.setTimeout(() => setUndoing(false), 1500);
  };

  return (
    <div
      className="mx-1 my-2 overflow-hidden rounded-2xl border border-border/80 bg-surface/70 animate-slide-up"
      role="region"
      aria-label="Last edit diff"
    >
      <div className="flex items-center justify-between gap-2 border-b border-border/60 px-3.5 py-2.5">
        <div className="min-w-0">
          <p className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
            <FileDiff className="h-3.5 w-3.5 text-accent" aria-hidden="true" />
            Changes from last edit
          </p>
          <p className="mt-0.5 text-[11px] text-muted">
            {lastEditDiff.filesChanged.length} file
            {lastEditDiff.filesChanged.length === 1 ? "" : "s"} updated
            {lastEditDiff.message ? ` · ${lastEditDiff.message}` : ""}
          </p>
        </div>
        {lastEditDiff.canUndo && onUndo ? (
          <button
            type="button"
            onClick={handleUndo}
            disabled={undoing}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-amber-500/30 bg-amber-500/10 px-2.5 py-1.5 text-[11px] font-medium text-amber-200 transition-colors hover:bg-amber-500/15 disabled:opacity-50"
          >
            <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
            {undoing ? "Undoing…" : "Undo last edit"}
          </button>
        ) : null}
      </div>
      <ul className="max-h-64 space-y-1 overflow-y-auto p-2">
        {lastEditDiff.diffs.map((file) => {
          const open = expandedPath === file.path;
          return (
            <li key={file.path} className="rounded-xl border border-border/50 bg-background/40">
              <button
                type="button"
                onClick={() => setExpandedPath(open ? null : file.path)}
                className="flex w-full items-center gap-2 px-2.5 py-2 text-left text-[12px]"
              >
                <span
                  className={cn(
                    "rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase",
                    file.status === "added" && "bg-emerald-500/15 text-emerald-300",
                    file.status === "removed" && "bg-red-500/15 text-red-300",
                    file.status === "modified" && "bg-accent/15 text-accent",
                    !["added", "removed", "modified"].includes(file.status) &&
                      "bg-surface text-muted",
                  )}
                >
                  {file.status}
                </span>
                <span className="min-w-0 flex-1 truncate font-mono text-[11px] text-foreground">
                  {file.path}
                </span>
                {open ? (
                  <ChevronUp className="h-3.5 w-3.5 text-muted" aria-hidden="true" />
                ) : (
                  <ChevronDown className="h-3.5 w-3.5 text-muted" aria-hidden="true" />
                )}
              </button>
              {open && file.diff ? (
                <pre className="max-h-48 overflow-auto border-t border-border/50 bg-[#0b1220] p-2 font-mono text-[10px] leading-relaxed text-slate-200">
                  {file.diff.split("\n").map((line, index) => (
                    <div
                      key={`${file.path}-${index}`}
                      className={cn(
                        line.startsWith("+") && !line.startsWith("+++") && "text-emerald-300",
                        line.startsWith("-") && !line.startsWith("---") && "text-red-300",
                        line.startsWith("@@") && "text-sky-300",
                      )}
                    >
                      {line || " "}
                    </div>
                  ))}
                  {file.truncated ? (
                    <div className="mt-1 text-muted">… diff truncated</div>
                  ) : null}
                </pre>
              ) : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
