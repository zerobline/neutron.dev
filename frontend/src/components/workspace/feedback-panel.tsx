"use client";

import { useState } from "react";
import { CheckCircle, RotateCcw, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Avatar } from "@/components/ui/avatar";
import { useProjectStore } from "@/stores/project-store";
import { AGENTS, type PhaseResult } from "@/types";
import { PhaseResultCard } from "./phase-result-card";

interface FeedbackPanelProps {
  onFeedback: (action: "approve" | "revise", feedback?: string) => void;
}

export function FeedbackPanel({ onFeedback }: FeedbackPanelProps) {
  const pending = useProjectStore((s) => s.pendingFeedback);
  const [showRevise, setShowRevise] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [revisionText, setRevisionText] = useState("");

  if (!pending) return null;

  const agent = AGENTS.find((a) => a.id === pending.agent);
  const phaseLabel: Record<string, string> = {
    leading: "Leadership",
    analyzing: "Analysis",
    planning: "Planning",
    architecting: "Architecture",
    building: "Engineering",
  };

  const previewResult: PhaseResult | null = pending.spec || pending.headline || pending.summary
    ? {
        id: "pending-feedback",
        phase: pending.phase,
        agent: pending.agent,
        kind: pending.kind || "markdown",
        headline:
          pending.headline
          || `${phaseLabel[pending.phase] || pending.phase} ready for review`,
        summary: pending.summary || pending.content,
        content: pending.content,
        spec: pending.spec || null,
        hasStructuredSpec: Boolean(pending.spec),
        // Stable preview id — not used for ordering; avoid impure Date.now() in render.
        timestamp: 0,
      }
    : null;

  const handleApprove = () => {
    setShowRevise(false);
    setRevisionText("");
    onFeedback("approve");
  };

  const handleRevise = () => {
    setShowRevise(false);
    setRevisionText("");
    onFeedback("revise", revisionText.trim());
  };

  return (
    <div className="mx-4 mb-3 rounded-xl border border-accent/30 bg-accent/5 p-4 animate-slide-up">
      <div className="mb-3 flex items-center gap-2">
        {agent && <Avatar name={agent.name} color={agent.color} size="sm" />}
        <div className="flex-1">
          <p className="text-sm font-medium text-foreground">
            {phaseLabel[pending.phase] ?? pending.phase} Review
          </p>
          <p className="text-xs text-muted">
            {agent?.name} has finished — review before continuing
          </p>
        </div>
        {Boolean(pending.content || previewResult) && (
          <button
            type="button"
            onClick={() => setShowPreview(!showPreview)}
            className="flex items-center gap-1 text-xs text-accent transition-colors hover:text-accent/80"
          >
            {showPreview ? (
              <><ChevronUp className="h-3 w-3" />Hide output</>
            ) : (
              <><ChevronDown className="h-3 w-3" />Show output</>
            )}
          </button>
        )}
      </div>

      {showPreview && previewResult ? (
        <div className="mb-3 max-h-80 overflow-y-auto rounded-lg border border-border bg-background/40 p-2">
          <PhaseResultCard result={previewResult} />
        </div>
      ) : null}

      {showPreview && !previewResult && pending.content ? (
        <div className="mb-3 max-h-60 overflow-y-auto rounded-lg border border-border bg-background/50 p-3 text-xs">
          <p className="whitespace-pre-wrap break-words text-foreground/90">{pending.content}</p>
        </div>
      ) : null}

      {showRevise ? (
        <div className="space-y-2">
          <Textarea
            value={revisionText}
            onChange={(e) => setRevisionText(e.target.value)}
            placeholder="Describe what you'd like changed..."
            rows={3}
            autoFocus
          />
          <div className="flex gap-2">
            <Button size="sm" onClick={handleRevise} disabled={!revisionText.trim()}>
              <RotateCcw className="h-3.5 w-3.5 mr-1.5" />
              Send Revision
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => { setShowRevise(false); setRevisionText(""); }}
            >
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex gap-2">
          <Button size="sm" onClick={handleApprove}>
            <CheckCircle className="h-3.5 w-3.5 mr-1.5" />
            Approve & Continue
          </Button>
          <Button size="sm" variant="secondary" onClick={() => setShowRevise(true)}>
            <RotateCcw className="h-3.5 w-3.5 mr-1.5" />
            Request Revision
          </Button>
        </div>
      )}
    </div>
  );
}
