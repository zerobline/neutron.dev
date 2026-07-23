"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, Sparkles } from "lucide-react";
import { Avatar } from "@/components/ui/avatar";
import { looksLikeJsonBlob } from "@/lib/humanize";
import { cn } from "@/lib/utils";
import { useProjectStore } from "@/stores/project-store";
import { AGENTS } from "@/types";

function StreamBody({ stream }: { stream: string }) {
  const scrollerRef = useRef<HTMLPreElement>(null);
  // Parent only mounts StreamBody for non-empty, non-JSON streams.
  const clean = stream.trim();
  const [expanded, setExpanded] = useState(true);

  useEffect(() => {
    if (!expanded) return;
    // Ref is set after commit when the stream <pre> is mounted.
    const node = scrollerRef.current;
    /* v8 ignore next -- defensive null guard for first-paint races */
    if (!node) return;
    node.scrollTop = node.scrollHeight;
  }, [stream, expanded]);

  const longStream = clean.length > 280;

  return (
    <div className="mt-3 border-t border-border/50 pt-2.5">
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="group mb-1.5 inline-flex items-center gap-1.5 text-[11px] font-medium text-muted transition-colors hover:text-foreground"
        aria-expanded={expanded}
      >
        <Sparkles className="h-3 w-3 text-accent/80" aria-hidden="true" />
        Reasoning
        <ChevronDown
          className={cn(
            "h-3 w-3 transition-transform duration-200",
            expanded && "rotate-180",
          )}
          aria-hidden="true"
        />
      </button>
      {expanded ? (
        <div className="relative">
          <pre
            ref={scrollerRef}
            className={cn(
              "max-h-44 overflow-y-auto whitespace-pre-wrap break-words rounded-xl border border-border/60 bg-background/50 px-3 py-2.5 font-mono text-[11px] leading-relaxed text-muted",
              longStream && "stream-mask-top",
            )}
          >
            {clean}
            <span
              className="ml-0.5 inline-block h-3 w-[2px] translate-y-0.5 bg-accent align-middle animate-stream-caret"
              aria-hidden="true"
            />
          </pre>
        </div>
      ) : (
        <p className="line-clamp-2 text-[11px] leading-relaxed text-muted/90">
          {clean}
        </p>
      )}
    </div>
  );
}

export function ThinkingIndicator({ embedded = false }: { embedded?: boolean }) {
  const thinkingMessages = useProjectStore((s) => s.thinkingMessages);

  if (thinkingMessages.size === 0) return null;

  return (
    <div className={cn(!embedded && "space-y-2")}>
      {Array.from(thinkingMessages.values()).map((thinking) => {
        const agent = AGENTS.find((a) => a.id === thinking.agent);
        if (!agent) return null;

        const stream = thinking.stream?.trim() ?? "";
        const hasStream = Boolean(stream) && !looksLikeJsonBlob(stream);

        const card = (
          <div
            key={thinking.agent}
            className={cn(
              "relative overflow-hidden rounded-2xl border border-border/80 bg-surface/70",
              !embedded && "animate-slide-up",
            )}
            style={{
              boxShadow: `inset 3px 0 0 0 ${agent.color}`,
            }}
          >
            <div className="pointer-events-none absolute inset-0 animate-soft-shimmer opacity-60" />
            <div className="relative flex gap-3 px-3.5 py-3">
              <Avatar name={agent.name} color={agent.color} size="sm" status="thinking" />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-xs font-semibold" style={{ color: agent.color }}>
                    {agent.name}
                  </p>
                  <span className="text-[10px] text-muted">{agent.role}</span>
                  <span className="inline-flex items-center gap-1 rounded-full border border-border/70 bg-background/50 px-1.5 py-0.5 text-[10px] font-medium text-muted">
                    <span className="relative flex h-1.5 w-1.5">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-40" />
                      <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-accent" />
                    </span>
                    Working
                  </span>
                </div>
                <div className="mt-1.5 flex items-start gap-2">
                  <span className="mt-1.5 inline-flex shrink-0 gap-0.5" aria-hidden="true">
                    <span className="h-1 w-1 animate-bounce rounded-full bg-current opacity-50 [animation-delay:0ms]" />
                    <span className="h-1 w-1 animate-bounce rounded-full bg-current opacity-50 [animation-delay:150ms]" />
                    <span className="h-1 w-1 animate-bounce rounded-full bg-current opacity-50 [animation-delay:300ms]" />
                  </span>
                  <p className="text-[13px] leading-snug text-foreground/90" role="status">
                    {thinking.content}
                  </p>
                </div>
                {hasStream ? <StreamBody stream={stream} /> : null}
              </div>
            </div>
          </div>
        );

        if (embedded) return card;

        return (
          <div key={thinking.agent} className="px-1 py-1">
            {card}
          </div>
        );
      })}
    </div>
  );
}
