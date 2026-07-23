"use client";

import { useState } from "react";
import Markdown from "react-markdown";
import { AlertTriangle, ChevronDown, ChevronUp } from "lucide-react";
import { Avatar } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";
import { getAgentBgColor } from "@/lib/utils";
import { ArtifactCard } from "./artifact-card";
import { PhaseResultCard } from "./phase-result-card";
import { AGENTS, type Message } from "@/types";

const COLLAPSE_THRESHOLD = 1500;

export function MessageBubble({ message }: { message: Message }) {
  const agent = message.agent ? AGENTS.find((a) => a.id === message.agent) : null;
  const [expanded, setExpanded] = useState(false);
  const isLong = message.content.length > COLLAPSE_THRESHOLD;

  if (message.role === "system") {
    if (message.kind === "error") {
      const failedAgent = message.agent ? AGENTS.find((a) => a.id === message.agent) : null;
      return (
        <div className="py-3 animate-slide-up">
          <div className="rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm max-w-[90%] mx-auto">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 rounded-full bg-red-500/20 p-1.5 text-red-400">
                <AlertTriangle className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-red-300">Build stopped</p>
                <p className="mt-1 text-foreground">{message.content}</p>
                {(failedAgent || message.phase || message.category) && (
                  <div className="mt-2 flex flex-wrap gap-1.5 text-[11px] text-muted">
                    {failedAgent && <span className="rounded-full border border-border bg-background/40 px-2 py-0.5">{failedAgent.name}</span>}
                    {message.phase && <span className="rounded-full border border-border bg-background/40 px-2 py-0.5">{message.phase}</span>}
                    {message.category && <span className="rounded-full border border-border bg-background/40 px-2 py-0.5">{message.category}</span>}
                  </div>
                )}
                {message.nextAction && (
                  <p className="mt-3 rounded-lg border border-border bg-background/40 px-3 py-2 text-xs text-muted">
                    Next: {message.nextAction}
                  </p>
                )}
                {message.details && message.details !== message.content && (
                  <details className="mt-2 text-xs text-muted">
                    <summary className="cursor-pointer text-accent">Show technical details</summary>
                    <pre className="mt-2 whitespace-pre-wrap break-words rounded-lg bg-background/60 p-2">{message.details}</pre>
                  </details>
                )}
              </div>
            </div>
          </div>
        </div>
      );
    }

    const fileMatch = message.content.match(/^Created file: (.+)$/);
    if (fileMatch) {
      return (
        <div className="py-2 animate-slide-up">
          <ArtifactCard filePath={fileMatch[1]} />
        </div>
      );
    }

    return (
      <div className="flex justify-center py-2 animate-slide-up">
        <span className="text-xs text-muted bg-surface/50 px-3 py-1 rounded-full border border-border">
          {message.content}
        </span>
      </div>
    );
  }

  if (message.role === "user") {
    return (
      <div className="flex justify-end py-2 animate-slide-up">
        <div className="max-w-[80%] rounded-2xl rounded-br-md bg-accent px-4 py-3 text-sm text-white">
          {message.content}
        </div>
      </div>
    );
  }

  // Legacy persisted stream fragments are intentionally hidden. They are raw
  // provider output, not a reliable or useful representation of model reasoning.
  if (message.kind === "thinking") return null;

  if (message.kind === "phase_result" && message.phaseResult) {
    return <PhaseResultCard result={message.phaseResult} />;
  }

  const displayContent = isLong && !expanded
    ? message.content.slice(0, COLLAPSE_THRESHOLD)
    : message.content;

  return (
    <div className="flex gap-3 py-2 animate-slide-up">
      {agent && (
        <Avatar name={agent.name} color={agent.color} size="sm" />
      )}
      <div className="flex-1 min-w-0">
        {agent && (
          <p className="text-xs font-medium mb-1" style={{ color: agent.color }}>
            {agent.name} — {agent.role}
          </p>
        )}
        <div
          className={cn(
            "rounded-2xl rounded-tl-md px-4 py-3 text-sm border max-w-[90%]",
            agent ? getAgentBgColor(agent.id) : "bg-surface border-border"
          )}
        >
          <div className={cn(
            "prose prose-sm prose-invert max-w-none break-words [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 agent-prose",
            isLong && !expanded && "line-clamp-none"
          )}>
            <Markdown>{displayContent}</Markdown>
            {isLong && !expanded && (
              <span className="text-muted">...</span>
            )}
          </div>
          {isLong && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="flex items-center gap-1 mt-2 text-xs text-accent hover:text-accent/80 transition-colors"
            >
              {expanded ? (
                <>
                  <ChevronUp className="h-3 w-3" />
                  Show less
                </>
              ) : (
                <>
                  <ChevronDown className="h-3 w-3" />
                  Show full output
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
