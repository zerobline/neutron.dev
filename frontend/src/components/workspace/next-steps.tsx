"use client";

import { useState } from "react";
import {
  AtSign,
  CheckCircle2,
  Circle,
  Download,
  FileCode2,
  RotateCcw,
  Sparkles,
  Wand2,
} from "lucide-react";
import { downloadProject } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useProjectStore } from "@/stores/project-store";
import type { FollowUpSuggestion } from "@/types";

const FALLBACK_SUGGESTIONS: FollowUpSuggestion[] = [
  {
    id: "mock_data",
    label: "Fill with mock data",
    prompt:
      "@engineer Fill the app with realistic mock data so tables, cards, lists, and charts look populated on first load.",
  },
  {
    id: "dark_mode",
    label: "Add dark mode",
    prompt:
      "@engineer Add a polished dark mode toggle and persist the preference in localStorage.",
  },
  {
    id: "mobile",
    label: "Improve mobile",
    prompt:
      "@engineer Improve mobile layout and touch-friendly navigation without breaking desktop.",
  },
  {
    id: "polish",
    label: "Polish the UI",
    prompt:
      "@engineer Polish spacing, typography, and empty states so the UI feels production-ready.",
  },
];

interface NextStepsProps {
  projectId?: string;
  onSend: (message: string, targetAgent?: "engineer" | import("@/types").AgentName) => void;
  onInsertMention?: () => void;
  onUndo?: () => void;
}

/**
 * Post-build surface: quality checklist, files changed, and one-click follow-ups.
 * Designed to keep people iterating instead of bouncing after the first generate.
 */
export function NextSteps({ projectId, onSend, onInsertMention, onUndo }: NextStepsProps) {
  const projectStatus = useProjectStore((s) => s.projectStatus);
  const lastCompletion = useProjectStore((s) => s.lastCompletion);
  const lastEditDiff = useProjectStore((s) => s.lastEditDiff);
  const files = useProjectStore((s) => s.files);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  if (projectStatus !== "complete") return null;

  const suggestions =
    lastCompletion?.suggestions && lastCompletion.suggestions.length > 0
      ? lastCompletion.suggestions
      : FALLBACK_SUGGESTIONS;
  const checklistItems = lastCompletion?.checklist?.items ?? [];
  const filesChanged = lastCompletion?.filesChanged ?? [];
  const allFiles =
    lastCompletion?.files && lastCompletion.files.length > 0
      ? lastCompletion.files
      : files.map((f) => f.file_path);
  const isIterate = lastCompletion?.mode === "iterate";
  const headline = isIterate ? "Update applied" : "Build complete";
  const subcopy =
    lastCompletion?.message ||
    (isIterate
      ? "Ravi updated your project. Review the preview, then keep shaping it."
      : "Your files are ready. Keep iterating with Ravi — no full re-plan required.");

  const runSuggestion = (suggestion: FollowUpSuggestion) => {
    const prompt = suggestion.prompt.startsWith("@")
      ? suggestion.prompt
      : `@engineer ${suggestion.prompt}`;
    onSend(prompt, "engineer");
  };

  const handleDownload = async () => {
    if (!projectId) return;
    setExporting(true);
    setExportError(null);
    try {
      await downloadProject(projectId);
    } catch {
      setExportError("Download failed — try Export in the preview toolbar.");
    } finally {
      setExporting(false);
    }
  };

  return (
    <div
      className="mx-1 my-3 overflow-hidden rounded-2xl border border-emerald-500/25 bg-gradient-to-b from-emerald-500/[0.08] to-surface/40 shadow-[0_8px_30px_rgba(0,0,0,0.08)] animate-slide-up"
      role="region"
      aria-label="Next steps after build"
    >
      <div className="border-b border-border/60 px-4 py-3">
        <div className="flex items-start gap-2.5">
          <span className="mt-0.5 flex h-7 w-7 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-emerald-300">{headline}</p>
            <p className="mt-0.5 text-xs leading-relaxed text-muted">{subcopy}</p>
            <p className="mt-1 text-[10px] text-muted/90">
              Tip: in the preview, click <span className="font-medium text-foreground/80">Select to edit</span>, then click any UI element.
            </p>
          </div>
          <div className="flex shrink-0 flex-col gap-1.5">
            {projectId ? (
              <button
                type="button"
                onClick={() => void handleDownload()}
                disabled={exporting}
                className="inline-flex items-center gap-1.5 rounded-lg border border-border/80 bg-background/50 px-2.5 py-1.5 text-[11px] font-medium text-foreground transition-colors hover:border-accent/30 hover:bg-accent/10 hover:text-accent disabled:opacity-50"
              >
                <Download className="h-3.5 w-3.5" aria-hidden="true" />
                {exporting ? "Preparing…" : "Download ZIP"}
              </button>
            ) : null}
            {(lastCompletion?.canUndo || lastEditDiff?.canUndo) && onUndo ? (
              <button
                type="button"
                onClick={onUndo}
                className="inline-flex items-center gap-1.5 rounded-lg border border-amber-500/30 bg-amber-500/10 px-2.5 py-1.5 text-[11px] font-medium text-amber-200 transition-colors hover:bg-amber-500/15"
              >
                <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
                Undo last edit
              </button>
            ) : null}
          </div>
        </div>
        {exportError ? (
          <p className="mt-2 text-[11px] text-red-400">{exportError}</p>
        ) : null}
      </div>

      {checklistItems.length > 0 ? (
        <div className="border-b border-border/50 px-4 py-3">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-muted">
            Quality check
          </p>
          <ul className="grid gap-1.5 sm:grid-cols-2">
            {checklistItems.map((item) => (
              <li
                key={item.id}
                className="flex items-start gap-2 rounded-lg border border-border/50 bg-background/30 px-2.5 py-2"
              >
                {item.ok ? (
                  <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400" aria-hidden="true" />
                ) : (
                  <Circle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-400/80" aria-hidden="true" />
                )}
                <span className="min-w-0">
                  <span className={cn("block text-[12px] font-medium", item.ok ? "text-foreground" : "text-amber-200/90")}>
                    {item.label}
                  </span>
                  {item.detail ? (
                    <span className="mt-0.5 block text-[10px] leading-snug text-muted">{item.detail}</span>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {(filesChanged.length > 0 || allFiles.length > 0) ? (
        <div className="border-b border-border/50 px-4 py-3">
          <p className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-muted">
            <FileCode2 className="h-3 w-3" aria-hidden="true" />
            {filesChanged.length > 0 ? "Files changed" : "Project files"}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {(filesChanged.length > 0 ? filesChanged : allFiles).slice(0, 12).map((path) => (
              <span
                key={path}
                className="inline-flex max-w-full truncate rounded-md border border-border/70 bg-background/50 px-2 py-0.5 font-mono text-[10px] text-foreground/90"
                title={path}
              >
                {path}
              </span>
            ))}
            {(filesChanged.length > 0 ? filesChanged : allFiles).length > 12 ? (
              <span className="text-[10px] text-muted">
                +{(filesChanged.length > 0 ? filesChanged : allFiles).length - 12} more
              </span>
            ) : null}
          </div>
        </div>
      ) : null}

      <div className="px-4 py-3">
        <p className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-muted">
          <Wand2 className="h-3 w-3" aria-hidden="true" />
          Try next
        </p>
        <div className="flex flex-wrap gap-2">
          {suggestions.map((suggestion) => (
            <button
              key={suggestion.id}
              type="button"
              onClick={() => runSuggestion(suggestion)}
              className="inline-flex items-center gap-1.5 rounded-full border border-accent/25 bg-accent/10 px-3 py-1.5 text-[11px] font-medium text-accent transition-colors hover:border-accent/40 hover:bg-accent/15 focus:outline-none focus:ring-2 focus:ring-accent/40"
            >
              {suggestion.label}
            </button>
          ))}
          {onInsertMention ? (
            <button
              type="button"
              onClick={onInsertMention}
              className="inline-flex items-center gap-1.5 rounded-full border border-border/80 bg-background/40 px-3 py-1.5 text-[11px] font-medium text-muted transition-colors hover:border-border hover:text-foreground focus:outline-none focus:ring-2 focus:ring-accent/30"
            >
              <AtSign className="h-3 w-3" aria-hidden="true" />
              Custom edit
            </button>
          ) : null}
        </div>
        <p className="mt-2.5 text-[10px] leading-relaxed text-muted/90">
          Tips run as focused @engineer edits — planning and architecture are skipped so you stay in flow.
        </p>
      </div>
    </div>
  );
}
